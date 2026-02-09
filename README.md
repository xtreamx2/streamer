# Streamer Audio – Raspberry Pi I2S DAC + OLED

Streamer Audio to otwarto‑źródłowy projekt odtwarzacza audio opartego na Raspberry Pi, z obsługą:
- DAC I2S (PCM5102A / Hifiberry DAC)
- MPD/MPC
- OLED SSD1306/SSD1309
- Automatycznego testu audio
- Modularnej konfiguracji (gpio.json)
- Instalatora z pełnym logowaniem i autodetekcją

Projekt jest rozwijany z naciskiem na:
- przejrzystość,
- automatyzację,
- dokumentację,
- łatwość modyfikacji,
- pełną audytowalność zmian.

---

## 📦 Funkcje

- Automatyczna instalacja MPD, MPC, Python, bibliotek i GStreamera
- Autodetekcja Raspberry Pi, DAC I2S i OLED
- Automatyczna konfiguracja `/boot/firmware/config.txt`
- Wyłączenie wbudowanego audio (dtparam=audio=on)
- Generowanie testowego pliku `test.wav` (800 Hz / 0.5 s)
- Test DAC z pominięciem MPD
- Dodanie polskiej stacji radiowej (Radio 357)
- Logowanie wszystkich kroków do `streamer/logs/install.log`
- Tworzenie `gpio.json` jako centralnego źródła konfiguracji
- Przenoszenie instalatora do `streamer/installer/`
- Aktualizacja `change_log`

---

## 🧰 Wymagania sprzętowe

- Raspberry Pi 1 -5 / Zero W / Zero 2 W / CM4
- DAC I2S PCM5102A lub kompatybilny (Hifiberry DAC)
- OLED SSD1306/SSD1309 (I2C, adres 0x3C)
- Zasilanie 5V
- Połączenia I2S:
    - BCK → GPIO18
    - LRCK → GPIO19
    - DIN → GPIO21
    - GND → GND
    - VIN → 5V

---

## 🖥️ Wymagania systemowe

- Raspberry Pi OS Bookworm lub nowszy
- Dostęp do internetu
- Uprawnienia sudo

---

## 🚀 Instalacja

### Instalacja przez `curl`

```bash
curl -s https://raw.githubusercontent.com/xtreamx2/streamer/Second/install.sh | bash | tee install.log
chmod +x install.sh
./install.sh


/streamer
│
├── main.py              # główny loop
├── config.py            # ustawienia
│
├── audio/
│   ├── player.py        # MPD/Spotify/BT/Radio
│   ├── dsp.py           # EQ, loudness, filtry (CamillaDSP/ALSA)
│   └── volume.py        # głośność (PCM5122 + soft)
│
├── ui/
│   ├── display.py       # OLED
│   ├── menu.py          # logika menu
│   └── encoder.py       # enkoder + przyciski
│
├── hardware/
│   ├── relays.py        # przekaźniki/tyrystory
│   ├── rtc.py           # DS3231 (później)
│   └── power.py         # standby, mute, itp.
│
└── utils/
└── logger.py        # logi


Projekt składa się z trzech warstw licencyjnych:

Element	Licencja
Hardware (schematy, PCB)	CERN-OHL-S
Oprogramowanie (skrypty, Python)	GPLv3
Dokumentacja (README, opisy)	CC-BY-SA 4.0


Roadmap
Integracja enkodera i przycisków

Obsługa wielu DAC (PCM5122, ES9023)

Tryb „standalone” bez sieci

WebUI do konfiguracji

Automatyczne aktualizacje

🐞 Zgłaszanie błędów
Zgłoszenia i propozycje zmian mile widziane w Issues.
=======
# Streamer



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://raw.githubusercontent.com/xtreamx2/streamer/Second/install.sh
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.com/aloisy/streamer/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
* [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
>>>>>>> origin/main
