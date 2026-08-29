from voice_input import VoiceInput


voice = VoiceInput()

while True:
    command = input(
        "\nPress Enter to speak, or type q to quit: "
    ).strip()

    if command.lower() == "q":
        break

    text = voice.listen()

    if text:
        print()
        print(f"You > {text}")
    else:
        print()
        print("[Voice] Nothing recognized.")