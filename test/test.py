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

@cocotb.test()
async def test_score_increment(dut):
    """Pressing the active segment button increments the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock
    dut.ui_in.value = 0  # Buttons mapped to ui_in
    await reset_dut(dut)

    active_idx = await wait_active(dut)

    # Pulse the correct button
    dut.ui_in.value = 1 << active_idx
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    score = dut.uio_out.value.integer  # Score LEDs mapped to uio_out
    assert score == 1, f"Expected score 1, got {score}"

@cocotb.test()
async def test_no_increment_on_wrong(dut):
    """Pressing a non-active button does not change the score."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock

    dut.ui_in.value = 0
    await reset_dut(dut)

    # Settle
    for _ in range(5):
        await RisingEdge(dut.clk)

    # Identify active segment
    seg_val = dut.uo_out.value.integer & 0x7F
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
    """Test that the 7-segment display shows the correct active segment pattern during gameplay."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())  # 1MHz clock
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Score two correct presses
    for _ in range(2):
        idx = await wait_active(dut)
        dut.ui_in.value = 1 << idx
        await RisingEdge(dut.clk)
        await Timer(1, units='ns')
        dut.ui_in.value = 0

    score = dut.uio_out.value.integer
    assert score == 2, f"Expected internal score 2, got {score}"

    # Wait for the next active segment to appear
    await RisingEdge(dut.clk)
    await Timer(1, units='ns')

    # Check that the display shows an active segment pattern (one bit should be 0)
    seg_val = dut.uo_out.value.integer & 0x7F
    dp = (dut.uo_out.value.integer >> 7) & 1
    
    # During gameplay (game_end=0), exactly one segment should be active (0)
    active_segments = [i for i in range(7) if ((seg_val >> i) & 1) == 0]
    assert len(active_segments) == 1, f"Expected exactly one active segment, got {len(active_segments)}: {active_segments}"
    assert dp == 1, f"Expected dp=1 (game running), got {dp}"
    
    # Verify the active segment is valid (0-6)
    active_idx = active_segments[0]
    assert 0 <= active_idx <= 6, f"Active segment index {active_idx} is out of range [0-6]"

@cocotb.test()
async def test_game_timer(dut):
    """Test that the game ends after the timer expires and displays the score."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())  # Faster clock for simulation
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Score some points before timer expires
    for _ in range(3):
        idx = await wait_active(dut)
        dut.ui_in.value = 1 << idx
        await RisingEdge(dut.clk)
        await Timer(1, units='ns')
        dut.ui_in.value = 0
        await RisingEdge(dut.clk)

    # Wait for game to end (simulation mode uses 1500 cycles instead of 15M)
    print(f"Starting timer test at {dut.clk.value}")
    print("Waiting for timer in simulation mode...")
    
    # Wait for 1500 cycles plus margin
    cycles_per_print = 100  # Print status frequently
    
    for i in range(2000):  # Added margin for safety
        await RisingEdge(dut.clk)
        if i % cycles_per_print == 0:
            time_in_sec = i/1_000_000  # Convert cycles to seconds
            # Print debug info
            print(f"\nTime elapsed: {time_in_sec:.1f} sec (cycle {i})")
            print(f"    Clock: {dut.clk.value}")
            print(f"    Game end: {dut.game_end.value}")
            print(f"    Score: {dut.uio_out.value.integer}")
            
        if dut.game_end.value:
            print("\nGAME END DETECTED!")
            print(f"Game ended at {i/1_000_000:.3f} seconds ({i} cycles)")
            print(f"Final score: {dut.uio_out.value.integer}")
            
            # Wait a few cycles to ensure game_end stays high
            for _ in range(100):
                await RisingEdge(dut.clk)
                if not dut.game_end.value:
                    raise TestFailure("game_end signal dropped after being set")
            break
    else:
        raise TestFailure("Game did not end within expected time")

    # Verify game end state
    assert dut.game_end.value == 1, "Game should be in end state"
    
    # Check that display shows score
    score = dut.uio_out.value.integer
    assert score == 3, f"Expected final score 3, got {score}"
    
    # Verify decimal point is off in score display mode
    dp = (dut.uo_out.value.integer >> 7) & 1
    assert dp == 0, f"Expected dp=0 (game end), got {dp}"