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
        seg_val = dut.uo_out.value.integer & 0x7F  # Get 7-segment display bits [6:0]
        zeros = [i for i in range(7) if ((seg_val >> i) & 1) == 0]
        if zeros:
            return zeros[0]
    raise TestFailure(f"No active segment within {max_cycles} cycles; last seg=0b{seg_val:07b}")

def is_game_over(dut):
    """Returns True if the game is over (dp is off)."""
    return (dut.uo_out.value.integer >> 7) & 1 == 0

@cocotb.test()
async def test_score_increment(dut):
    """Pressing the active segment button increments the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock
    dut.ui_in.value = 0
    await reset_dut(dut)

    active_idx = await wait_active(dut)

    # Press button and hold for 5 cycles to pass debouncing
    dut.ui_in.value = 1 << active_idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    # Wait a few cycles for FSM to process the debounced press
    for _ in range(3):
        await RisingEdge(dut.clk)

    score = dut.uio_out.value.integer
    assert score == 1, f"Expected score 1, got {score}"

@cocotb.test()
async def test_no_increment_on_wrong(dut):
    """Pressing a non-active button does not change the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    for _ in range(5):
        await RisingEdge(dut.clk)

    seg_val = dut.uo_out.value.integer & 0x7F
    active_idx = next(i for i in range(7) if ((seg_val >> i) & 1) == 0)
    wrong_idx = (active_idx + 1) % 8

    dut.ui_in.value = 1 << wrong_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    assert dut.uio_out.value.integer == 0, f"Score changed on wrong press: got {dut.uio_out.value.integer}"

@cocotb.test()
async def test_game_end_display(dut):
    """Test that the 7-segment display shows the correct active segment pattern during gameplay."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    for _ in range(2):
        idx = await wait_active(dut)
        dut.ui_in.value = 1 << idx
        for _ in range(5):
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        for _ in range(3):
            await RisingEdge(dut.clk)

    score = dut.uio_out.value.integer
    assert score == 2, f"Expected internal score 2, got {score}"

    await RisingEdge(dut.clk)
    await Timer(1, units='ns')

    seg_val = dut.uo_out.value.integer & 0x7F
    dp = (dut.uo_out.value.integer >> 7) & 1
    
    active_segments = [i for i in range(7) if ((seg_val >> i) & 1) == 0]
    assert len(active_segments) == 1, f"Expected exactly one active segment, got {len(active_segments)}: {active_segments}"
    assert dp == 1, f"Expected dp=1 (game running), got {dp}"

@cocotb.test()
async def test_button_debounce_filter(dut):
    """Test that button glitches are filtered out by the debouncer."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    active_idx = await wait_active(dut)
    
    dut.ui_in.value = 1 << active_idx
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    score = dut.uio_out.value.integer
    assert score == 0, f"Score changed on glitch: got {score}, expected 0"

@cocotb.test()
async def test_button_debounce_stable(dut):
    """Test that stable button presses are registered after debounce period."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    active_idx = await wait_active(dut)
    
    dut.ui_in.value = 1 << active_idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    dut.ui_in.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    
    score = dut.uio_out.value.integer
    assert score == 1, f"Score not incremented after stable press: got {score}, expected 1"

@cocotb.test()
async def test_game_timer(dut):
    """Test that the game ends after the timer expires and displays the score."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    for _ in range(3):
        idx = await wait_active(dut)
        dut.ui_in.value = 1 << idx
        for _ in range(5):
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        for _ in range(3):
            await RisingEdge(dut.clk)

    for i in range(2000):
        await RisingEdge(dut.clk)
        if is_game_over(dut):
            break
    else:
        raise TestFailure("Game did not end within expected time")

    assert is_game_over(dut), "Game should be in end state"
    
    score = dut.uio_out.value.integer
    assert score == 3, f"Expected final score 3, got {score}"
    
    dp = (dut.uo_out.value.integer >> 7) & 1
    assert dp == 0, f"Expected dp=0 (game end), got {dp}"

@cocotb.test()
async def test_auto_start_on_reset(dut):
    """After reset (without pressing start), the game should auto-start and light one segment."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    await RisingEdge(dut.clk)
    seg_val = dut.uo_out.value.integer & 0x7F
    assert seg_val != 0x7F, f"Segment did not light after reset: {seg_val:07b}"

@cocotb.test()
async def test_restart_after_game_over(dut):
    """After timer expiry and GAME_OVER, pressing pb0 restarts the game."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    while not is_game_over(dut):
        await RisingEdge(dut.clk)

    active = await wait_active(dut)
    wrong = (active + 1) % 8
    dut.ui_in.value = 1 << wrong
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Score changed in GAME_OVER"

    dut.ui_in.value = 1 << 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0

    idx = await wait_active(dut)
    assert 0 <= idx <= 6, "No segment lit after restart"

@cocotb.test()
async def test_one_second_lockout(dut):
    """Verify that after wrong-press lockout lasts ~1s, then clears."""
    cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    idx = await wait_active(dut)
    wrong = (idx + 1) % 8

    dut.ui_in.value = 1 << wrong
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Lockout failed—score incremented too early"

    sim_cycles = 10 + 2
    for _ in range(sim_cycles):
        await RisingEdge(dut.clk)

    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    assert dut.uio_out.value.integer == 1, "Lockout did not clear after 1 second"

@cocotb.test()
async def test_lockout_independent_buttons(dut):
    """Locking out one wrong button should not block other buttons."""
    cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    idx = await wait_active(dut)
    wrong1 = (idx + 1) % 8
    wrong2 = (idx + 2) % 8

    dut.ui_in.value = 1 << wrong1
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    dut.ui_in.value = 1 << wrong2
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Correct button registered during multi‐button lockout"

    for _ in range(12):
        await RisingEdge(dut.clk)

    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 1, "Multi‐button lockout did not clear"