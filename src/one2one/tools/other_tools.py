import os
import subprocess

from one2one.core import One2OneTool, One2OneToolsCollection, console
from one2one.tools.others.android_attack import AndroidAttackTools
from one2one.tools.others.email_verifier import EmailVerifyTools
from one2one.tools.others.hash_crack import HashCrackingTools
from one2one.tools.others.homograph_attacks import IDNHomographAttackTools
from one2one.tools.others.mix_tools import MixTools
from one2one.tools.others.payload_injection import PayloadInjectorTools
from one2one.tools.others.socialmedia import SocialMediaBruteforceTools
from one2one.tools.others.socialmedia_finder import SocialMediaFinderTools
from one2one.tools.others.web_crawling import WebCrawlingTools
from one2one.tools.others.wifi_jamming import WifiJammingTools

from rich.panel import Panel
from rich.prompt import Prompt


class HatCloud(One2OneTool):
    TITLE = "HatCloud(Bypass CloudFlare for IP)"
    MAINTENANCE = "stale"
    MAINTENANCE_NOTE = "no push in 2y 11m"
    DESCRIPTION = "HatCloud build in Ruby. It makes bypass in CloudFlare for " \
                  "discover real IP."
    INSTALL_COMMANDS = ["git clone https://github.com/HatBashBR/HatCloud.git"]
    PROJECT_URL = "https://github.com/HatBashBR/HatCloud"

    def run(self):
        from one2one.config import get_tools_dir
        from rich.prompt import Prompt
        site = Prompt.ask("Enter Site")
        # Bug 3 fix: os.chdir() replaced with cwd= parameter
        subprocess.run(
            ["sudo", "ruby", "hatcloud.rb", "-b", site],
            cwd=str(get_tools_dir() / "HatCloud"),
        )


class OtherTools(One2OneToolsCollection):
    TITLE = "Other tools"
    TOOLS = [
        SocialMediaBruteforceTools(),
        AndroidAttackTools(),
        HatCloud(),
        IDNHomographAttackTools(),
        EmailVerifyTools(),
        HashCrackingTools(),
        WifiJammingTools(),
        SocialMediaFinderTools(),
        PayloadInjectorTools(),
        WebCrawlingTools(),
        MixTools()
    ]

if __name__ == "__main__":
    tools = OtherTools()
    tools.show_options()
