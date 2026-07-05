"""
Skills module — registers all built-in skills on import.
"""

from app.skills.registry import get_registry
from app.skills.builtin.calculator import CalculatorSkill
from app.skills.builtin.datetime_skill import DatetimeSkill
from app.skills.builtin.web_search_skill import WebSearchSkill
from app.skills.builtin.read_file_skill import ReadFileSkill
from app.skills.builtin.code_executor import CodeExecutorSkill
from app.skills.builtin.pdf_reader import PDFReaderSkill
from app.skills.builtin.github_search import GitHubSearchSkill
from app.skills.builtin.package_installer import PackageInstallerSkill
from app.skills.builtin.vision_skill import VisionSkill
from app.skills.builtin.shell_skill import ShellSkill
from app.skills.builtin.computer_skill import OpenAppSkill, FindFilesSkill, ReadAnywhereSkill


def _register_builtins() -> None:
    reg = get_registry()
    reg.register(CalculatorSkill())
    reg.register(DatetimeSkill())
    reg.register(WebSearchSkill())
    reg.register(ReadFileSkill())
    reg.register(CodeExecutorSkill())
    reg.register(PDFReaderSkill())
    reg.register(GitHubSearchSkill())
    reg.register(PackageInstallerSkill())
    reg.register(VisionSkill())
    reg.register(ShellSkill())
    reg.register(OpenAppSkill())
    reg.register(FindFilesSkill())
    reg.register(ReadAnywhereSkill())


_register_builtins()
