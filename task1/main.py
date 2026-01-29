# main.py
"""CLI интерфейс Coding Agent"""

from logger import log


def main():
    log.info("=" * 50)
    log.info("Coding Agent")
    log.info("=" * 50)
    print("Введите сообщение или 'exit' для выхода\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("До свидания!")
                break

            if not user_input:
                continue

            from agent import run_agent
            run_agent(user_input)

            log.separator()

        except KeyboardInterrupt:
            print("\nДо свидания!")
            break


if __name__ == "__main__":
    main()
