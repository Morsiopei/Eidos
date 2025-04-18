```python
# src/ai/prompt_builder.py

def build_transition_prompt(current_node_label, node_output_summary, potential_next_nodes, user_specs):
    """
    Constructs the core text prompt for the AI transition decision.
    Assumes node_output_summary is a string representation.
    """
    prompt = f"You are an execution flow controller for a simulation model.\n"
    prompt += f"Current state: Just finished executing node '{current_node_label}'.\n"
    prompt += f"Output Data Summary from '{current_node_label}':\n---\n{node_output_summary}\n---\n\n"

    if not potential_next_nodes:
        prompt += "TASK: This is a terminal node (no outgoing paths). Respond with the exact word NONE."
        return prompt

    prompt += "Potential next nodes (choose based on ID):\n"
    for node_id, info in potential_next_nodes.items():
        # Provide ID, Label, Type, and Description
        prompt += (f"- ID: {node_id}, Label: {info.get('label', 'N/A')}, "
                   f"Type: {info.get('type', 'Default')}, "
                   f"Desc: {info.get('description', 'N/A')}\n")

    prompt += "\nDECISION GUIDANCE:\n"
    if user_specs:
        prompt += f"User Specifications:\n'''\n{user_specs}\n'''\n"
    else:
        # Improved default guidance
        prompt += ("Default: Analyze the output data summary and the potential next nodes. "
                   "Choose the node ID(s) that represent the most logical continuation of the process "
                   "based on node types, descriptions, and the data produced. "
                   "Consider cause-and-effect, state changes, or feedback loops.\n")

    prompt += "\nTASK: Based *only* on the information provided above, which node ID(s) should be executed next? "
    prompt += "Respond ONLY with the chosen node ID(s), separated by commas if multiple. "
    prompt += "If no node should be executed based on the guidance and data, respond with the exact word NONE."
    return prompt
``` 
