from langchain.agents import create_agent
from agents.gcp.tools import get_ip_gcp
from agents.shared.models import model
from langchain_community.tools import ShellTool

shell_tool = ShellTool(
    ask_human_input=True
)

local_agent = create_agent(
    model=model,
    tools=[shell_tool],
    system_prompt=(
        "You are a bash shell assistan agent.\n\n"
        "INSTRUCTIONS:\n"
        "- Assist ONLY with bash-related tasks, DO NOT do any action related to other shells\n"
        "- After you're done with your tasks, respond to the supervisor directly\n"
        "- Respond ONLY with the results of your work, do NOT include ANY other text." 
    ),
    name="local_agent",
)
