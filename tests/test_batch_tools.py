import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from mcp_devtools.command_catalog import DESIGNER_CAPABILITIES, IBCMD_CAPABILITIES
from mcp_devtools.designer_runner import run_designer_batch
from mcp_devtools.ibcmd_runner import discover_ibcmd, run_ibcmd
from mcp_devtools.onec_batch import apply_xml_and_build_cf


class BatchToolsTests(unittest.TestCase):
    def test_catalogs_are_non_empty_and_unique(self):
        self.assertEqual(len({x.name for x in DESIGNER_CAPABILITIES}), len(DESIGNER_CAPABILITIES))
        self.assertEqual(len({x.name for x in IBCMD_CAPABILITIES}), len(IBCMD_CAPABILITIES))
        self.assertIn("dump_xml", {x.name for x in DESIGNER_CAPABILITIES})
        self.assertIn("config.apply", {x.name for x in IBCMD_CAPABILITIES})

    def test_designer_command_uses_designer_and_f(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            exe = root / "1cv8.exe"
            exe.write_bytes(b"exe")
            log = root / "run.log"
            log.write_text("ok", encoding="utf-8")
            runner = Mock(return_value=Mock(returncode=0))
            result = run_designer_batch(
                onec_executable=exe,
                connection_mode="file",
                connection=root,
                arguments=["/DumpCfg", root / "out.cf"],
                log_path=log,
                runner=runner,
            )
            command = runner.call_args.args[0]
            self.assertEqual(command[1:4], ["DESIGNER", "/F", str(root)])
            self.assertEqual(result.exit_code, 0)

    def test_mutating_ibcmd_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            exe = Path(root) / "ibcmd.exe"
            exe.write_bytes(b"exe")
            with self.assertRaises(PermissionError):
                run_ibcmd(ibcmd_executable=exe, arguments=["infobase", "config", "apply"])

    def test_ibcmd_help_is_read_only_and_redacts_password(self):
        with tempfile.TemporaryDirectory() as root:
            exe = Path(root) / "ibcmd.exe"
            exe.write_bytes(b"exe")
            runner = Mock(return_value=Mock(returncode=0, stdout=b"help", stderr=b""))
            result = discover_ibcmd(exe, runner=runner)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("help", result.stdout)

    def test_apply_build_fails_fast_before_load_when_backup_fails(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            exe = root / "1cv8.exe"
            exe.write_bytes(b"exe")
            ib = root / "ib"
            ib.mkdir()
            (ib / "1Cv8.1CD").write_bytes(b"db")
            source = root / "src"
            source.mkdir()
            (source / "Configuration.xml").write_text("<Configuration/>", encoding="utf-8")
            runner = Mock(return_value=Mock(returncode=1))
            with self.assertRaises(RuntimeError):
                apply_xml_and_build_cf(
                    onec_executable=exe,
                    infobase=ib,
                    source_dir=source,
                    output_cf=root / "out.cf",
                    runner=runner,
                )
            self.assertEqual(runner.call_count, 1)


if __name__ == "__main__":
    unittest.main()
