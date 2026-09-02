import sys
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.graph import build_research_graph
from src.config import is_langsmith_configured

console = Console()

def run_research(task: str, enable_hitl: bool = False):
    console.print(Panel(f'[bold cyan]Research Topic:[/bold cyan] {task}', title='Autonomous Research Engine', expand=False))
    
    if is_langsmith_configured():
        console.print('[dim green]LangSmith tracing active. Traces will be uploaded automatically.[/dim green]')
    else:
        console.print('[dim yellow]LangSmith API key not detected. Running locally.[/dim yellow]')
    
    # Compile graph with thread checkpointer
    app = build_research_graph(checkpointer=True, human_in_the_loop=enable_hitl)
    thread_id = str(uuid.uuid4())
    config = {'configurable': {'thread_id': thread_id}}
    
    initial_state = {
        'task': task,
        'plan': [],
        'research_data': [],
        'critique_feedback': None,
        'critique_passed': False,
        'revision_count': 0,
        'max_revisions': 2,
        'final_report': None
    }
    
    console.print(f'\n[bold yellow]Streaming Workflow Execution (Thread: {thread_id[:8]}):[/bold yellow]\n')
    
    # Stream events from LangGraph
    for output in app.stream(initial_state, config=config, stream_mode='updates'):
        for node_name, node_output in output.items():
            if node_name == 'planner':
                queries = node_output.get('plan', [])
                console.print(f'[bold blue]>> [Planner][/bold blue] Formulated {len(queries)} search sub-queries:')
                for q in queries:
                    console.print(f'   - {q}')
                    
            elif node_name == 'researcher':
                data = node_output.get('research_data', [])
                console.print(f'[bold green]>> [Researcher][/bold green] Collected {len(data)} search results.')
                
            elif node_name == 'fact_checker':
                passed = node_output.get('critique_passed', False)
                feedback = node_output.get('critique_feedback', '')
                rev = node_output.get('revision_count', 0)
                status_color = 'green' if passed else 'red'
                status_text = 'PASSED' if passed else 'NEEDS REVISION'
                console.print(f'[bold {status_color}]>> [Fact-Checker - Iteration {rev}][/bold {status_color}] Status: {status_text}')
                console.print(f'   [dim]Critique Feedback: {feedback}[/dim]')
                
            elif node_name == 'writer':
                console.print('[bold magenta]>> [Writer][/bold magenta] Synthesizing comprehensive research report...')
    
    # Retrieve final state
    final_state = app.get_state(config).values
    final_report = final_state.get('final_report', 'No report generated.')
    
    console.print('\n' + '='*80 + '\n')
    console.print(Panel(Markdown(final_report), title='Final Research & Fact-Check Report', border_style='cyan'))
    
    # Save to file
    filename = 'latest_research_report.md'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_report)
    console.print(f'\n[green]Report saved to {filename}[/green]\n')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
    else:
        query = console.input('[bold yellow]Enter research topic / question:[/bold yellow] ')
        if not query.strip():
            query = 'Recent advances in Small Language Models (SLMs) and on-device AI in 2026'
            
    run_research(query)
