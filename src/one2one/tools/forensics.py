import os

from one2one.core import One2OneTool, One2OneToolsCollection, console

from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt


class Autopsy(One2OneTool):
    TITLE = "Autopsy"
    DESCRIPTION = "Autopsy is a platform that is used by Cyber Investigators.\n" \
                  "[!] Works in any OS\n" \
                  "[!] Recover Deleted Files from any OS & Media \n" \
                  "[!] Extract Image Metadata"
    RUN_COMMANDS = ["sudo autopsy"]

    def __init__(self):
        super().__init__(installable=False)


class Wireshark(One2OneTool):
    TITLE = "Wireshark"
    DESCRIPTION = "Wireshark is a network capture and analyzer \n" \
                  "tool to see what’s happening in your network.\n " \
                  "And also investigate Network related incident"
    RUN_COMMANDS = ["sudo wireshark"]

    def __init__(self):
        super().__init__(installable=False)


class BulkExtractor(One2OneTool):
    TITLE = "Bulk extractor"
    DESCRIPTION = "Extract useful information without parsing the file system"
    PROJECT_URL = "https://github.com/simsong/bulk_extractor"
    SUPPORTED_OS = ["linux"]

    def __init__(self):
        super().__init__([
            ('GUI Mode (Download required)', self.gui_mode),
            ('CLI Mode', self.cli_mode)
        ], installable=False, runnable=False)

    def gui_mode(self):
        import subprocess
        from one2one.config import get_tools_dir
        console.print(Panel(Text(self.TITLE, justify="center"), style="bold magenta"))
        console.print("[bold magenta]Cloning repository and attempting to run GUI...[/]")
        tools_dir = get_tools_dir()
        subprocess.run(["git", "clone", "https://github.com/simsong/bulk_extractor.git"],
                       cwd=str(tools_dir))
        be_dir = tools_dir / "bulk_extractor"
        subprocess.run(["./BEViewer"], cwd=str(be_dir / "java_gui"))
        console.print(
            "[magenta]If you get an error after clone go to /java_gui/src/ and compile the .jar file && run ./BEViewer[/]")
        console.print(
            "[magenta]Please visit for more details about installation: https://github.com/simsong/bulk_extractor[/]")

    def cli_mode(self):
        import subprocess
        console.print(Panel(Text(self.TITLE + " - CLI Mode", justify="center"), style="bold magenta"))
        subprocess.run(["sudo", "apt", "install", "-y", "bulk-extractor"])
        console.print("[magenta]bulk_extractor [options] imagefile[/]")
        subprocess.run(["bulk_extractor", "-h"])


class Guymager(One2OneTool):
    TITLE = "Disk Clone and ISO Image Acquire"
    MAINTENANCE = "manual"
    MAINTENANCE_NOTE = "non-GitHub host — check by hand"
    DESCRIPTION = "Guymager is a free forensic imager for media acquisition."
    SUPPORTED_OS = ["linux"]
    INSTALL_COMMANDS = ["sudo apt install guymager"]
    RUN_COMMANDS = ["sudo guymager"]
    SYSTEM_PKGS = {"which": "guymager", "apt": "guymager"}
    PROJECT_URL = "https://guymager.sourceforge.io/"



class Toolsley(One2OneTool):
    TITLE = "Toolsley"
    MAINTENANCE = "manual"
    MAINTENANCE_NOTE = "non-GitHub host — check by hand"
    DESCRIPTION = "Toolsley got more than ten useful tools for investigation.\n" \
                  "[+]File signature verifier\n" \
                  "[+]File identifier \n" \
                  "[+]Hash & Validate \n" \
                  "[+]Binary inspector \n " \
                  "[+]Encode text \n" \
                  "[+]Data URI generator \n" \
                  "[+]Password generator"
    PROJECT_URL = "https://www.toolsley.com/"

    def __init__(self):
        super().__init__(installable=False, runnable=False)


class Volatility3(One2OneTool):
    TITLE = "Volatility 3 (Memory Forensics)"
    DESCRIPTION = (
        "The world's most widely used memory forensics framework.\n"
        "Usage: python3 vol.py -f memory.dmp windows.pslist"
    )
    INSTALL_COMMANDS = [
        "git clone https://github.com/volatilityfoundation/volatility3.git",
        "cd volatility3 && pip install --user -r requirements.txt",
    ]
    PROJECT_URL = "https://github.com/volatilityfoundation/volatility3"

    def run(self):
        from one2one.config import get_tools_dir
        import subprocess
        from rich.prompt import Prompt
        dump = Prompt.ask("Enter path to memory dump")
        plugin = Prompt.ask("Enter plugin", default="windows.pslist")
        subprocess.run(
            ["python3", "vol.py", "-f", dump, plugin],
            cwd=str(get_tools_dir() / "volatility3"),
        )


class Binwalk(One2OneTool):
    TITLE = "Binwalk (Firmware Analysis)"
    DESCRIPTION = (
        "Analyze, reverse engineer, and extract firmware images.\n"
        "Usage: binwalk -e firmware.bin"
    )
    INSTALL_COMMANDS = ["pip install --user binwalk"]
    RUN_COMMANDS = ["binwalk --help"]
    PROJECT_URL = "https://github.com/ReFirmLabs/binwalk"


class Pspy(One2OneTool):
    TITLE = "pspy (Process Monitor — No Root)"
    DESCRIPTION = "Monitor Linux processes without root — detects cron jobs, scheduled tasks, other users' commands."
    INSTALL_COMMANDS = [
        "curl -sSL https://github.com/DominicBreuker/pspy/releases/latest/download/pspy64 -o pspy",
        "chmod +x pspy",
    ]
    RUN_COMMANDS = ["./pspy --help"]
    PROJECT_URL = "https://github.com/DominicBreuker/pspy"
    SUPPORTED_OS = ["linux"]


class ForensicTools(One2OneToolsCollection):
    TITLE = "Forensic tools"
    TOOLS = [
        Autopsy(),
        Wireshark(),
        BulkExtractor(),
        Guymager(),
        Toolsley(),
        Volatility3(),
        Binwalk(),
        Pspy(),
    ]

if __name__ == "__main__":
    tools = ForensicTools()
    tools.show_options()
