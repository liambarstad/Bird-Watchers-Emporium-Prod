import logging

from graphs.consts import MAX_STEPS
from state import CoTState
from utils.llm import call_llama_server

logger = logging.getLogger(__name__)


def agent_node(state: CoTState) -> CoTState:
    next_step = state['step'] + 1
    
    reasoning_context = '\n'.join(state['reasoning_steps']) if state['reasoning_steps'] else 'No previous reasoning yet.'
    
    prompt = (
        f'You are performing chain-of-thought reasoning.\n' 
        f'Question: {state['question']}\n'
        f'Previous reasoning steps: {reasoning_context}\n'
        f'Step {next_step}: Think about the question and provide your reasoning for this step. Be concise but thoughtful.'
    )

    new_reason = call_llama_server([{'role': 'user', 'content': prompt}])
    logger.info(f'Agent reasoning step {next_step} completed')

    return {
        **state,
        'step': next_step,
        'reasoning_steps': [*state['reasoning_steps'], new_reason],
    }


def should_continue(state: CoTState) -> str:
    if state['step'] < MAX_STEPS:
        return 'continue'
    return 'finalize'


def finalize_node(state: CoTState) -> CoTState:
    reasoning_summary = '\n\n'.join(
        [f'Step {i+1}: {step}' for i, step in enumerate(state['reasoning_steps'])]
    )
    
    prompt = (
        f'Based on the following chain-of-thought reasoning, provide a clear and concise final answer to the question.\n'
        f'Question: {state['question']}\n'
        f'Reasoning steps:\n{reasoning_summary}\n'
        f'Final Answer: Provide a clear, direct answer to the question based on the reasoning above.'
    )

    messages = [{'role': 'user', 'content': prompt}]
    answer = call_llama_server(messages)
    logger.info(f'Final answer generated successfully')

    return {**state, 'answer': answer}