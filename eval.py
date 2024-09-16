from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith.evaluation import evaluate, LangChainStringEvaluator
from langsmith.schemas import Run, Example
from openai import OpenAI
import json

from dotenv import load_dotenv
load_dotenv()

from langsmith.wrappers import wrap_openai
from langsmith import traceable

client = wrap_openai(OpenAI())

ASSESSMENT_PROMPT = """
### Instructions

Please evaluate the Japanese language tutor bot using the following two key metrics. For each metric, provide a score from 1 to 5, where 1 indicates very poor performance and 5 indicates excellent performance. Include a concise sentence explaining the reason for each score.

1. **Language Proficiency Assessment**:
    - Score (1-5): [Your Score]
    - Explanation: [Provide a concise sentence explaining the accuracy and appropriateness of the language instruction, including grammar, vocabulary, and error correction.]

2. **Learning Effectiveness**:
    - Score (1-5): [Your Score]
    - Explanation: [Provide a concise sentence explaining the bot’s ability to engage learners, enhance their learning experience, and support their progress effectively.]

The output format is described below. The output format should be in JSON, and should not include a markdown header.

### Example Output:

{{
    "language_proficiency": [
        {{
            "score": "{score}",
            "reason": "{reason}"
        }}
    ],
    "learning_effectiveness": [
        {{
            "score": "{score}",
            "reason": "{reason}"
        }}
    ]
}}
"""

@traceable
def language_proficiency_evaluator(run: Run, example: Example) -> dict:
    inputs = example.inputs['input']
    outputs = example.outputs['output']

    # Extract system prompt
    system_prompt = next((msg['data']['content'] for msg in inputs if msg['type'] == 'system'), "")

    # Extract message history
    message_history = []
    for msg in inputs:
        if msg['type'] in ['human', 'ai']:
            message_history.append({
                "role": "user" if msg['type'] == 'human' else "assistant",
                "content": msg['data']['content']
            })

    # Extract latest user message and model output
    latest_message = message_history[-1]['content'] if message_history else ""
    model_output = outputs['data']['content']

    evaluation_prompt = f"""
    System Prompt: {system_prompt}

    Message History:
    {json.dumps(message_history, indent=2)}

    Latest User Message: {latest_message}

    Model Output: {model_output}

    Based on the above information, assess the model's output in terms of grammatical correctness, vocabulary use, and fluency in Japanese considering clarity and naturalness in communication.
    Provide a score from 0 to 10, where 0 is completely misunderstanding and 10 is completely correct Japanese language.
    Also provide a brief explanation of the reasoning for the score, focusing on accuracy and fluency of the language used.

    Respond in the following JSON format:
    {{
        "score": <int>,
        "explanation": "<string>"
    }}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI assistant tasked with evaluating the compliance of model outputs to given prompts and conversation context."},
            {"role": "user", "content": evaluation_prompt}
        ],
        temperature=0.2
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return {
            "key": "language_proficiency",
            "score": result["score"] / 10,  # Normalize to 0-1 range
            "reason": result["explanation"]
        }
    except json.JSONDecodeError:
        return {
            "key": "language_proficiency",
            "score": 0,
            "reason": "Failed to parse evaluator response"
        }

@traceable
def learning_effectiveness_evaluator(run: Run, example: Example) -> dict:
    inputs = example.inputs['input']
    outputs = example.outputs['output']

    # Extract system prompt
    system_prompt = next((msg['data']['content'] for msg in inputs if msg['type'] == 'system'), "")

    # Extract message history
    message_history = []
    for msg in inputs:
        if msg['type'] in ['human', 'ai']:
            message_history.append({
                "role": "user" if msg['type'] == 'human' else "assistant",
                "content": msg['data']['content']
            })

    # Extract latest user message and model output
    latest_message = message_history[-1]['content'] if message_history else ""
    model_output = outputs['data']['content']

    evaluation_prompt = f"""
    System Prompt: {system_prompt}

    Message History:
    {json.dumps(message_history, indent=2)}

    Latest User Message: {latest_message}

    Model Output: {model_output}

    Based on the above information, evaluate the model's ability to engage the learner and provide constructive feedback. Consider how well the bot personalizes the learning experience, including the relevance of exercises and adaptability to the learner’s language level.
    Provide a score from 0 to 10, where 0 is completely misunderstanding and 10 is completely understanding the context of the conversation.
    Also provide a brief explanation of the reasoning for the score, focusing on specific, actionalbe feedback and user engagement.

    Respond in the following JSON format:
    {{
        "score": <int>,
        "explanation": "<string>"
    }}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI assistant tasked with evaluating the compliance of model outputs to given prompts and conversation context."},
            {"role": "user", "content": evaluation_prompt}
        ],
        temperature=0.2
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return {
            "key": "learning_effectiveness",
            "score": result["score"] / 10,  # Normalize to 0-1 range
            "reason": result["explanation"]
        }
    except json.JSONDecodeError:
        return {
            "key": "learning_effectiveness",
            "score": 0,
            "reason": "Failed to parse evaluator response"
        }
    
# The name or UUID of the LangSmith dataset to evaluate on.
data = "Japanese Dataset"

# A string to prefix the experiment name with.
experiment_prefix = "initial-evaluation-2"

# List of evaluators to score the outputs of target task
evaluators = [
    language_proficiency_evaluator,
    learning_effectiveness_evaluator
]

# Evaluate the target task
results = evaluate(
    lambda inputs: inputs,
    data=data,
    evaluators=evaluators,
    experiment_prefix=experiment_prefix,
)

print(results)