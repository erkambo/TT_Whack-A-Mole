import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.result import TestFailure
import random

async def reset_dut(dut):
    """Assert reset for 100 ns, then release and wait one cycle."""
    dut.rst_n.value = 0
    await Timer(100, units='ns')
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def wait_active(dut, max_cycles=20):
    """Wait until a segment lights (one seg bit == 0), return its index."""
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        seg_val = dut.uo_out.value.integer & 0x7F  # Extract 7-segment display from uo_out[6:0]
        zeros = [i for i in range(7) if ((seg_val >> i) & 1) == 0]
        if zeros:
            return zeros[0]
    raise TestFailure(f"No active segment within {max_cycles} cycles; last seg=0b{seg_val:07b}")

async def wait_pattern(dut, min_lit=1):
    """Wait for a pattern with at least min_lit bits set, return the pattern."""
    for _ in range(1000):
        await RisingEdge(dut.clk)
        pattern = dut.dut.pattern.value.integer
        if bin(pattern).count('1') >= min_lit:
            return pattern
    raise TestFailure(f"No pattern with at least {min_lit} bits set found.")

async def play_to_score(dut, target_score):
    """Play correct rounds until the score reaches target_score."""
    while dut.uio_out.value.integer < target_score:
        # Wait for a pattern
        await RisingEdge(dut.clk)
        pattern = dut.dut.pattern.value.integer
        if pattern == 0:
            continue
        # Press all lit buttons
        dut.ui_in.value = pattern
        await RisingEdge(dut.clk)
        await Timer(1, units='ns')
        dut.ui_in.value = 0
        await RisingEdge(dut.clk)

async def wait_for_pattern_change(dut, old_pattern):
    """Wait until the pattern changes from old_pattern."""
    for _ in range(1000):
        await RisingEdge(dut.clk)
        new_pattern = dut.dut.pattern.value.integer
        if new_pattern != old_pattern and new_pattern != 0:
            return new_pattern
    raise TestFailure("Pattern did not change after correct press.")

async def wait_some_cycles(dut, n=3):
    for _ in range(n):
        await RisingEdge(dut.clk)

async def wait_for_score_increment(dut, old_score, timeout=1000):
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        new_score = dut.uio_out.value.integer
        if new_score > old_score:
            return new_score
    raise TestFailure(f"Score did not increment from {old_score} within {timeout} cycles.")

async def press_pattern(dut, pattern, hold_cycles=5):
    print(f"[press_pattern] Pressing pattern: {pattern:07b}")
    dut.ui_in.value = pattern
    for _ in range(hold_cycles):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

@cocotb.test()
async def test_score_increment(dut):
    """Pressing the active segment button increments the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    active_idx = await wait_active(dut)

    # Pulse the correct button
    dut.ui_in.value = 1 << active_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    score = dut.uio_out.value.integer
    assert score == 1, f"Expected score 1, got {score}"

@cocotb.test()
async def test_no_increment_on_wrong(dut):
    """Pressing a non-active button does not change the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())

    dut.ui_in.value = 0
    await reset_dut(dut)

    # Settle
    for _ in range(5):
        await RisingEdge(dut.clk)

    # Identify active segment
    seg_val = dut.uo_out.value.integer & 0x7F  # Extract 7-segment display from uo_out[6:0]
    active_idx = next(i for i in range(7) if ((seg_val >> i) & 1) == 0)
    # Choose a different button (wrap-around to bit 7 if necessary)
    wrong_idx = (active_idx + 1) % 8

    dut.ui_in.value = 1 << wrong_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Score should remain zero
    assert dut.uio_out.value.integer == 0, (
        f"Score changed on wrong press: got {dut.uio_out.value.integer}"
    )
    
@cocotb.test()
async def test_game_end_display(dut):
    """When game_end=1, the 7-segment shows the lower hex digit of the score."""
    print('DUT attributes:', dir(dut))
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)
    # Play two correct rounds to get score=2
    for _ in range(2):
        # Wait for FSM's latched pattern
        while True:
            await RisingEdge(dut.clk)
            pattern = dut.dut.pattern_latched.value.integer
            if pattern != 0:
                break
        await wait_some_cycles(dut, 3)
        print(f"[test_game_end_display] FSM Latched Pattern: {pattern:07b}, Score before: {dut.uio_out.value.integer}")
        await press_pattern(dut, pattern, hold_cycles=5)
        new_score = await wait_for_score_increment(dut, dut.uio_out.value.integer - 1)
        print(f"[test_game_end_display] Score after: {new_score}")
        # Wait for latched pattern to change
        old_pattern = pattern
        for _ in range(1000):
            await RisingEdge(dut.clk)
            pattern = dut.dut.pattern_latched.value.integer
            if pattern != old_pattern and pattern != 0:
                break
        await wait_some_cycles(dut, 3)
    score = dut.uio_out.value.integer
    assert score == 2, f"Expected internal score 2, got {score}"
    # Wait for game_end to be asserted by timer (60,000 cycles at 1MHz = 60ms)
    for _ in range(100000):  # Wait for 60ms game timer
        await RisingEdge(dut.clk)
        if dut.dut.game_end.value == 1:
            break
    else:
        raise TestFailure("game_end was not asserted by timer!")
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
    seg_val = dut.uo_out.value.integer & 0x7F  # Extract 7-segment display from uo_out[6:0]
    dp = (dut.uo_out.value.integer >> 7) & 1  # Extract decimal point from uo_out[7]
    assert expected is not None, f"No pattern for score {score}"
    assert seg_val == expected, (
        f"7-seg mismatch: expected 0b{expected:07b}, got 0b{seg_val:07b}"
    )
    assert dp == 0, f"Expected dp=0, got {dp}"

@cocotb.test()
async def test_multi_segment_score(dut):
    """Score only increments when all lit buttons are pressed (multi-segment pattern)."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)
    await play_to_score(dut, 5)  # Enter multi-segment mode
    # Wait for FSM's latched pattern
    for _ in range(1000):
        await RisingEdge(dut.clk)
        pattern = dut.dut.pattern_latched.value.integer
        if bin(pattern).count('1') >= 2:
            break
    await wait_some_cycles(dut, 3)
    print(f"[test_multi_segment_score] FSM Latched Pattern: {pattern:07b}, Score before: {dut.uio_out.value.integer}")
    await press_pattern(dut, pattern, hold_cycles=5)
    new_score = await wait_for_score_increment(dut, dut.uio_out.value.integer - 1)
    print(f"[test_multi_segment_score] Score after: {new_score}")
    # Wait for latched pattern to change
    old_pattern = pattern
    for _ in range(1000):
        await RisingEdge(dut.clk)
        pattern = dut.dut.pattern_latched.value.integer
        if pattern != old_pattern and pattern != 0:
            break
    await wait_some_cycles(dut, 3)
    score = dut.uio_out.value.integer
    assert score >= 6, f"Expected score >= 6 after multi-segment press, got {score}"

@cocotb.test()
async def test_partial_press_no_score(dut):
    """Partial press of lit buttons does not increment score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)
    await play_to_score(dut, 5)
    pattern = await wait_pattern(dut, min_lit=2)
    # Press only one of the lit buttons
    for i in range(7):
        if (pattern >> i) & 1:
            dut.ui_in.value = 1 << i
            break
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    score = dut.uio_out.value.integer
    assert score == 5, f"Partial press should not increment score, got {score}"

@cocotb.test()
async def test_wrong_press_lockout(dut):
    """Pressing a button not in the pattern triggers lockout."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)
    await play_to_score(dut, 5)
    # Wait for FSM's latched pattern
    for _ in range(1000):
        await RisingEdge(dut.clk)
        pattern = dut.dut.pattern_latched.value.integer
        if bin(pattern).count('1') >= 2:
            break
    await wait_some_cycles(dut, 3)
    # Find a button not in the pattern
    for i in range(7):
        if not ((pattern >> i) & 1):
            wrong_btn = 1 << i
            break
    else:
        raise TestFailure("No unlit button found for wrong press test.")
    dut.ui_in.value = wrong_btn
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    lockout = dut.dut.lockout.value.integer
    assert (lockout & wrong_btn), f"Wrong button {wrong_btn} should be locked out, lockout={lockout:08b}"

@cocotb.test()
async def test_pattern_timeout(dut):
    """If round timer expires, pattern changes and score does not increment."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)
    await play_to_score(dut, 5)
    pattern = await wait_pattern(dut, min_lit=2)
    # Wait for round timer to expire (5,000 cycles for score 5 at 1MHz)
    for _ in range(10000):  # Add some margin for 1MHz clock
        await RisingEdge(dut.clk)
        if dut.dut.round_expired.value == 1:
            break
    else:
        raise TestFailure("Pattern did not time out!")
    score = dut.uio_out.value.integer
    assert score == 5, f"Score should not increment on pattern timeout, got {score}"
