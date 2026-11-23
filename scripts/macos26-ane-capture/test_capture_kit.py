"""Structure tests for the macOS-26 capture kit (issue #12 review fixes 1-3).

The kit itself only runs on macOS (ANECompiler private framework), so these
tests pin the staging and launch contract instead: hwx_normalise.cpp must be
staged and built, the sibling binary copied into each probe work dir, and
ane-compile-hwx must launch it directly (no shell) only for H16/H17 targets.
"""

from pathlib import Path

KIT = Path(__file__).parent
REPO = KIT.parent.parent


def test_run_capture_stages_hwx_normalise():
    lines = (KIT / "run_capture.sh").read_text().splitlines()
    scp_start = next(i for i, l in enumerate(lines) if l.startswith("scp"))
    scp_end = next(i for i, l in enumerate(lines) if "$HOST:" in l)
    stanza = "\n".join(lines[scp_start:scp_end + 1])
    assert "hwx_normalise.cpp" in stanza, \
        "run_capture.sh must stage tools/hwx_normalise.cpp"


def test_mint_probe_builds_and_copies_hwx_normalise():
    text = (KIT / "mint_probe.sh").read_text()
    assert "hwx_normalise.cpp" in text, "mint_probe.sh must compile the normaliser"
    assert "hwx-normalise" in text
    # the probe work dirs copy the sibling binary next to ane-compile-hwx
    cp = [l for l in text.splitlines() if l.strip().startswith("cp ")]
    assert any("hwx-normalise" in l and "ane-compile-hwx" in l for l in cp), \
        "mint_probe.sh must copy hwx-normalise into $WORK alongside ane-compile-hwx"
    # a failed normaliser build must fail the leg (BUILD_OK gate)
    gate = [l for l in text.splitlines() if "NORM_RC" in l]
    assert any("BUILD_RC" in l or "BUILD_OK" in l for l in gate), \
        "BUILD_OK must depend on the hwx-normalise build result"


def test_bridge_launches_normaliser_without_shell():
    for name in ("tools/ane-compile-hwx.mm",
                 "scripts/macos26-ane-capture/ane-compile-hwx.mm"):
        text = (REPO / name).read_text()
        assert "std::system" not in text, f"{name}: shell launch must go"
        assert "_NSGetExecutablePath" in text, \
            f"{name}: sibling lookup must use _NSGetExecutablePath"
        assert "NSTask" in text, f"{name}: must launch hwx-normalise via NSTask"


def test_bridge_gates_normalisation_on_h16_h17():
    for name in ("tools/ane-compile-hwx.mm",
                 "scripts/macos26-ane-capture/ane-compile-hwx.mm"):
        text = (REPO / name).read_text()
        assert '"h16"' in text and '"h17"' in text, \
            f"{name}: normalisation must be gated on the H16/H17 target arch"
        # H13/H14 targets must keep working with no normaliser present:
        # the gate reads the container subtype (7/9) directly.
        assert "subtype" in text, f"{name}: gate must fall back to the HWX subtype"


def test_bridge_copies_stay_in_sync():
    a = (REPO / "tools" / "ane-compile-hwx.mm").read_bytes()
    b = (REPO / "scripts/macos26-ane-capture/ane-compile-hwx.mm").read_bytes()
    assert a == b
