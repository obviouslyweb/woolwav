![Woolwav logo](icons/woolwav_icon-256.png)

# Woolwav - *Discord.py Audio Bot*

Woolwav is an audio streaming bot created using Discord.py that allows users to upload their own audio tracks to listen to them in voice channels, with support for a variety of audio filetypes, playlist features, looping tracks, and (theoretically) support for an infinite amount of tracks to be played.

## Features
- Play audio files from the bot's `audio` folder, with `.mp3`, `.wav`, `.ogg`, `.m4a`, and `.flac` supported. Add new files to the folder to make them available for playback without the need to restart.
- Queue audio files in order and loop tracks if desired. 
- Pausing mid-playback, stopping, and skipping songs entirely.
- See a list of available files to play with `/audio`.
- Optionally restrict commands to users with specified Discord roles through `.env`.
- Logs important events to a file in the `logs` directory for debugging and monitoring.
- Self-hostable on your own Discord bot account, allowing for the ability to add or edit features as you see fit.

## Setting up Woolwav

> [!IMPORTANT]
> Woolwav is a private audio bot designed for invite-only Discord servers. These steps explain how to create and host your own instance of the bot from scratch. **You must host it yourself**; there is no public invite link, and I am not liable for how the bot is used. By using this code, you agree to comply with Discord’s Terms of Service and accept full responsibility for anything resulting from its use. For more information regarding usage, please see the **Legal Disclaimers** section below.

### Setup instructions
1. Download [ffmpeg](https://ffmpeg.org/download.html) and add it to your PATH. You can download pre-compiled versions from other users or compile it yourself (although doing so is a complicated process).
2. Download and install [Python](https://www.python.org/downloads/), as well as add it to PATH. Versions 3.9 to 3.12 are confirmed to work well, but 3.13 and above may have slight compatibility issues with Discord.py, so you may encounter issues with that route.
3. Download the contents of this repository (`woolwav`) to your computer and store in a safe location (optimally somewhere quick and easy to access).
4. Log into the [Discord Developer Portal](https://discord.com/developers/applications) using your Discord account. Create a new application and give it a name. On the *Bot* page, toggle "Server Members Intent" and "Message Content Intent"; these are required for the bot to be able to properly process user information and messages to read messages.
5. In the main `woolwav` folder, create a new file called `.env`. This will contain important details that our bot needs to run. Type `DISCORD_TOKEN=` on one line. Back in the Discord Developer Portal *Bot* page, click "Reset Token", then paste your bot token after the `=`. This is necessary for the bot to be able to interface with Discord, so ensure that it's properly pasted. Save the file when done.
> [!WARNING]
> **Do NOT share your bot token or .env file with anyone!** If it's stolen, others can log in as this bot and do whatever they want with it under your Developer account.
6. If you only want certain users to be able to use the bot, add `ALLOWED_ROLES=` on another line in `.env` with comma-separated Discord role names (e.g. `ALLOWED_ROLES=Admin,Moderator,Volunteer`). Only users with one of these roles can use commands. If you omit `ALLOWED_ROLES` or leave it empty, any user will be able to use all commands. Save the file when done.
7. Install the required dependencies specified in `requirements.txt`. You can do this easily by opening Command Prompt, Terminal, or equivalent program on your device, navigate to the `woolwav` folder using `cd path/to/woolwav`, and run `pip install -r requirements.txt` to install all required Python libraries.
8. Return to your application on the Discord Developer Portal and go to the OAuth2 tab. Scroll down to *OAuth2 URL Generator*. This is where you'll create the invite link that you will use to invite the bot into your server. Toggle "bot", "applications.commands", and then under Bot Permissions, "View Channels", "Send Messages", "Send Messages in Threads", "Manage Messages", "Read Message History", "Add Reactions", "Connect", "Speak", and "Use Voice Activity". Then, under Integration Type, choose "Guild Install". Copy the Generated URL and store it so you can use it to reinvite the bot going forward.
9. Open the link with your Discord account, and select the server(s) you want to add it to. Once added, it will appear offline; this is because we've yet to turn the bot on.

## Using Woolwav

1. Using Command Prompt, Terminal, or an equivalent program, navigate to the `woolwav` folder using `cd your_path_to/woolwav`.
2. Type `python main.py` to turn the bot on. After a few seconds, the bot should load and display a message, `Logged in as (bot name)#1234 (ID: ####)`. Once you see this message, the bot will start accepting commands.
3. In Discord, type `/help` in any channel the bot can access to see the available slash commands.
4. To turn off the bot, use `CTRL + C` on the terminal window you used to run the bot. This will terminate the bot entirely. If using Command Prompt or Powershell, closing the window will also terminate the bot.

## Adding audio tracks

Find a compatible audio file (`.mp3`, `.wav`, `.ogg`, `.m4a`, or `.flac`) that you want to play. While not necessary, it's recommended to give it a short or easily memorable name, as users will have to repeat the filename in order to play the audio. **Make sure you're comfortable with the details in the filename, as these will be publicly visible to users interfacing with the bot!**

In the `audio` folder of the bot, place your files there. The bot will now be able to find and play audio from the folder. You can even add and remove tracks from there while the bot is still running, although removing a track while the bot is playing it may cause critical errors.

> [!TIP]
> You can also place additional subfolders in the `audio` folder. The bot will be able to play audio tracks from these. Use `/audio` to list the root folder, or `/audio` with the subfolder option (e.g. `my_music` or `my_music/jingles`) to browse inside a folder.

## Miscellaneous Information

### Contributors
* [obviouslyweb](https://github.com/obviouslyweb)

### Encounter a bug / have an idea / want to contribute?

Please don't hesitate to add an issue if you encounter a bug or have an idea for enhancement.

Contributors are welcome to add issues and suggest pull requests to improve the functionality of Woolwav! If you want something done, create an issue for it and connect a pull request to it. I'll take a look at it when I can. If you contribute, you'll be credited here!

### Development environment

To recreate the development environment, you need the following software and/or libraries with the specified versions:

* [Visual Studio Code](https://code.visualstudio.com/)
* [Python 3.11.5](https://www.python.org/downloads/)
* [discord.py 2.3.2](https://discordpy.readthedocs.io/en/stable/)
* [ffmpeg 7.7.1-full_build-www.gyan.dev](https://ffmpeg.org/)

### Resources used in development

I found these websites useful in developing this software:

* [discord.py](https://discordpy.readthedocs.io/en/stable/)'s documentation on the Python libraries used to create this application
* [Python Package Index - discord.py](https://pypi.org/project/discord.py/)
* [Discord Developer Documentation](https://discord.com/developers/docs/intro)

## Legal Disclaimers

*This project is provided “as is” without warranty of any kind. By using this code, you agree that you are solely responsible for compliance with Discord’s Terms of Service and all applicable laws. I accept no liability for misuse or damages.*

*Woolwav Logo © obviouslyweb 2026. You are permitted to use the logo for usage on your own instance of the bot, if desired.*

*This project makes use of several third-party libraries, each of which is subject to its own license. Key dependencies include [discord.py](https://pypi.org/project/discord.py/) for Discord bot functionality, [python-dotenv](https://pypi.org/project/python-dotenv/) for environment variable management, and [ffmpeg](https://ffmpeg.org/) for audio processing. Please consult the respective links for details on each library’s license terms and ensure compliance when using or modifying this project.*
