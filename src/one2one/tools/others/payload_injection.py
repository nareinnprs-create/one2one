from one2one.core import One2OneTool, One2OneToolsCollection, console

from rich.panel import Panel
from rich.prompt import Prompt
from rich import box


class DebInject(One2OneTool):
    ARCHIVED = True
    ARCHIVED_REASON = "Upstream repo archived by author (last commit 2022-04)"
    TITLE = "Debinject"
    DESCRIPTION = "Debinject is a tool that inject malicious code into *.debs"
    INSTALL_COMMANDS = [
        "git clone https://github.com/UndeadSec/Debinject.git"]
    RUN_COMMANDS = ["cd Debinject;python debinject.py"]
    PROJECT_URL = "https://github.com/UndeadSec/Debinject"


class Pixload(One2OneTool):
    TITLE = "Pixload"
    DESCRIPTION = "Pixload -- Image Payload Creating tools \n " \
                  "Pixload is Set of tools for creating/injecting payload into images."
    INSTALL_COMMANDS = [
        "sudo apt install libgd-perl libimage-exiftool-perl libstring-crc32-perl",
        "git clone https://github.com/chinarulezzz/pixload.git"
    ]
    PROJECT_URL = "https://github.com/chinarulezzz/pixload"

    def __init__(self):
        super().__init__(runnable = False)


class PayloadInjectorTools(One2OneToolsCollection):
    TITLE = "Payload Injector"
    TOOLS = [
        DebInject(),
        Pixload()
    ]

if __name__ == "__main__":
    tools = PayloadInjectorTools()
    tools.show_options()
