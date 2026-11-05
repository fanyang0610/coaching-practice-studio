import os

from coach_agent import CoachAgent
from coaching_core import CoachingState


def main():
    print("Welcome to the Coaching Practice Studio")
    print("Type 'quit' to exit, 'next' to manually force next stage, 'mode llm' or 'mode template' to swap modes.")
    print("Type 'key <API_KEY>' to set the API key for CLI LLM mode.")

    agent = CoachAgent(mode="template")
    api_key = os.environ.get("OPENAI_API_KEY", "")

    print(f"\n[Coach - {agent.current_state.name} ({agent.mode})]: {agent.generate_response('')}")

    while True:
        user_input = input("\n[Client]: ")

        if user_input.lower() in ["quit", "exit"]:
            print("Ending session. Goodbye!")
            break

        if user_input.lower() == "next":
            if agent.force_next_state():
                print(f"--- Manually transitioned to {agent.current_state.name} ---")
            else:
                print("--- Already at final stage ---")

            try:
                prompt = agent.get_stage_prompt(api_key=api_key or None)
                agent.context.append({"role": "coach", "content": prompt})
                print(f"\n[Coach - {agent.current_state.name} ({agent.mode})]: {prompt}")
            except Exception as exc:
                print(f"--- {exc} ---")
            continue

        if user_input.lower().startswith("mode "):
            new_mode = user_input.split(" ")[1]
            if agent.set_mode(new_mode):
                print(f"--- Switched to {new_mode} mode ---")
            else:
                print("--- Invalid mode. Use 'template' or 'llm' ---")
            continue

        if user_input.lower().startswith("key "):
            api_key = user_input[4:].strip()
            print("--- API key updated for this CLI session ---")
            continue

        try:
            response = agent.generate_response(user_input, api_key=api_key or None)
            print(f"\n[Coach - {agent.current_state.name} ({agent.mode})]: {response}")
        except Exception as exc:
            print(f"--- {exc} ---")

        if agent.current_state == CoachingState.CLOSING:
            break


if __name__ == "__main__":
    main()
