from one2one.core import One2OneTool, One2OneToolsCollection, console

from rich.panel import Panel
from rich.prompt import Prompt
from rich import box


class GoSpider(One2OneTool):
    TITLE = "Gospider"
    MAINTENANCE = "stale"
    MAINTENANCE_NOTE = "no push in 2y 3m"
    DESCRIPTION = "Gospider - Fast web spider written in Go"
    INSTALL_COMMANDS = ["sudo go get -u github.com/jaeles-project/gospider"]
    PROJECT_URL = "https://github.com/jaeles-project/gospider"

    def __init__(self):
        super().__init__(runnable = False)


class WebCrawlingTools(One2OneToolsCollection):
    TITLE = "Web crawling"
    TOOLS = [GoSpider()]

if __name__ == "__main__":
    tools = WebCrawlingTools()
    tools.show_options()
