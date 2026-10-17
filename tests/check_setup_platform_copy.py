#!/usr/bin/env python3
"""Check the wizard's platform-specific source contract without a compiler.

The release ZIP gate also checks the final compiled host strings. This small
source check isolates the Windows/POSIX branches so it can run on either host.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def platform_source(text, windows):
    enabled, stack, output = True, [], []
    for line in text.splitlines():
        match = re.match(r"\s*#if\s+(!?)defined\(_WIN32\)\s*$", line)
        if match:
            condition = windows != bool(match.group(1))
            stack.append((enabled, condition))
            enabled = enabled and condition
        elif re.match(r"\s*#else\s*$", line):
            parent, condition = stack[-1]
            enabled = parent and not condition
        elif re.match(r"\s*#endif\s*$", line):
            enabled, _ = stack.pop()
        elif line.lstrip().startswith("#"):
            raise ValueError("unhandled directive in bounded wizard region: " + line)
        elif enabled:
            output.append(line)
    if stack:
        raise ValueError("unclosed platform condition")
    return "\n".join(output)


class SetupPlatformTests(unittest.TestCase):
    def setUp(self):
        ui = (ROOT / "src/common/backends/imgui/launcher_imgui.cpp").read_text(encoding="utf-8")
        self.page = ui[ui.index("/* ---- Page 0: build tools"):ui.index("/* ---- Page 1: BIOS")]
        model = (ROOT / "src/common/launcher_model.c").read_text(encoding="utf-8")
        start = model.index("void launcher_model_start_ensure_toolchain(")
        self.job = model[start:model.index("void launcher_model_start_prepare_disc(", start)]

    def test_windows_keeps_download_zip_update_controls(self):
        page = platform_source(self.page, True)
        for token in ("1. Portable toolchain", "Download latest portable toolchain##tc",
                      "Select cmake-clang-v1 toolchain zip", "Skip for now##tc_skip"):
            self.assertIn(token, page)
        self.assertNotIn("1. Native build tools", page)
        job = platform_source(self.job, True)
        self.assertIn("g_prep_job.download = want_update ? 2 : 1", job)
        self.assertIn("g_prep_job.zip_path", job)

    def test_posix_shows_native_tools_and_never_requests_download_or_zip(self):
        page = platform_source(self.page, False)
        for token in ("1. Native build tools", "Install CMake, Ninja, Python 3",
                      "your package manager", "Check tools##tc_next"):
            self.assertIn(token, page)
        for token in ("portable toolchain", "cmake-clang-v1", "tc_skip", "toolchain zip"):
            self.assertNotIn(token, page)
        job = platform_source(self.job, False)
        self.assertIn("memset(&g_prep_job, 0", job)
        self.assertIn("Checking native build tools", job)
        self.assertNotIn("g_prep_job.download =", job)
        self.assertNotIn("g_prep_job.zip_path", job)
        self.assertIn("prep_spawn_thread(m)", job)


if __name__ == "__main__":
    unittest.main()
