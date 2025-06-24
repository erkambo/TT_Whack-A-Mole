import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.result import TestFailure

async def reset_dut(dut):
    """Asserting reset for 100 ns, then release and wait one cycle."""
    dut.rst_n.value = 0
    await Timer(100, units='ns')
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def wait_active(dut, max_cycles=20):
    """Wait until a segment lights (one seg bit == 0), return its index."""
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        seg_val = dut.seg.value.integer
        zeros = [i for i in range(7) if ((seg_val >> i) & 1) == 0]
        if zeros:
            return zeros[0]
    raise TestFailure(f"No active segment within {max_cycles} cycles; last seg=0b{seg_val:07b}")

@cocotb.test()
async def test_score_increment(dut):
    """Pressing the active segment button increments the score."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())
    dut.btn.value = 0
    dut.game_end.value = 0
    await reset_dut(dut)

    active_idx = await wait_active(dut)

    # Pulse the correct button
    dut.btn.value = 1 << active_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.btn.value = 0
    await RisingEdge(dut.clk)

    score = dut.led_score.value.integer
    assert score == 1, f"Expected score 1, got {score}"

@cocotb.test()
async def test_no_increment_on_wrong(dut):
    """Pressing a non-active button does not change the score."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())

    dut.btn.value = 0
    dut.game_end.value = 0
    await reset_dut(dut)

    # Settle
    for _ in range(5):
        await RisingEdge(dut.clk)

    # Identify active segment
    seg_val = dut.seg.value.integer
    active_idx = next(i for i in range(7) if ((seg_val >> i) & 1) == 0)
    # Choose a different button (wrap-around to bit 7 if necessary)
    wrong_idx = (active_idx + 1) % 8

    dut.btn.value = 1 << wrong_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.btn.value = 0
    await RisingEdge(dut.clk)

    # Score should remain zero
    assert dut.led_score.value.integer == 0, (
        f"Score changed on wrong press: got {dut.led_score.value.integer}"
    )
    
@cocotb.test()
async def test_game_end_display(dut):
    """When game_end=1, the 7-segment shows the lower hex digit of the score."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())
    dut.btn.value = 0
    dut.game_end.value = 0
    await reset_dut(dut)

    # Score two correct presses
    for _ in range(2):
        idx = await wait_active(dut)
        dut.btn.value = 1 << idx
        await RisingEdge(dut.clk)
        await Timer(1, units='ns')
        dut.btn.value = 0

    score = dut.led_score.value.integer
    assert score == 2, f"Expected internal score 2, got {score}"

    # Trigger game end and sample
    dut.game_end.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')

    # Map hex digit to segment pattern
    patterns = {
        0: 0b1000000,
        1: 0b1111001,
        2: 0b0100100,
        3: 0b0110000,
        4: 0b0011001,
        5: 0b0010010,
        6: 0b0000010,
        7: 0b1111000,
        8: 0b0000000,
        9: 0b0010000,
    }
    expected = patterns.get(score & 0xF)
    seg_val = dut.seg.value.integer
    dp = dut.dp.value.integer
    assert expected is not None, f"No pattern for score {score}"
    assert seg_val == expected, (
        f"7-seg mismatch: expected 0b{expected:07b}, got 0b{seg_val:07b}"
    )
    assert dp == 0, f"Expected dp=0, got {dp}"