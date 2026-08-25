"""
Scanner Agent — pulls batches of ANC observation records via CliniqBridge
(or the NDHS-shaped synthetic generator in demo mode). Deliberately simple:
this agent's job is data acquisition, not reasoning, so it's a lightweight
LlmAgent whose real work happens through its function tool.
"""

from google.adk.agents import Agent

from tools.cliniqbridge_tool import fetch_anc_observations

scanner_agent = Agent(
    name="scanner_agent",
    model="gemini-3.6-flash",
    instruction=(
        "You are the Scanner Agent in the ANC Fleet pipeline. Your only job is "
        "to call fetch_anc_observations to pull a batch of ANC records for "
        "processing. Do not analyze or score the records yourself — just fetch "
        "them and report the batch size and whether more records remain."
    ),
    tools=[fetch_anc_observations],
)
