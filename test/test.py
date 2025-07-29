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

    # Press button and hold for 5 cycles to pass debouncing
    dut.ui_in.value = 1 << active_idx
    for _ in range(5):  # More than DEBOUNCE_CYCLES
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    # Wait a few cycles for FSM to process the debounced press
    for _ in range(3):
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
        # Press button and hold for 5 cycles to pass debouncing
        dut.ui_in.value = 1 << idx
        for _ in range(5):  # More than DEBOUNCE_CYCLES
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        # Wait a few cycles for FSM to process the debounced press
        for _ in range(3):
            await RisingEdge(dut.clk)

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

@cocotb.test()
async def test_button_debounce_filter(dut):
    """Test that button glitches are filtered out by the debouncer."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Get the active segment
    active_idx = await wait_active(dut)
    
    # Create a glitch - button press for only 2 cycles (less than DEBOUNCE_CYCLES)
    dut.ui_in.value = 1 << active_idx
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    
    # Wait a few cycles to ensure the glitch is filtered
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    # Score should still be 0 since the glitch was filtered
    score = dut.uio_out.value.integer
    assert score == 0, f"Score changed on glitch: got {score}, expected 0"

@cocotb.test()
async def test_button_debounce_stable(dut):
    """Test that stable button presses are registered after debounce period."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Get the active segment
    active_idx = await wait_active(dut)
    
    # Press button and hold for 5 cycles (more than DEBOUNCE_CYCLES)
    dut.ui_in.value = 1 << active_idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    
    # Release button
    dut.ui_in.value = 0
    # Wait a few cycles for FSM to process the debounced press
    for _ in range(3):
        await RisingEdge(dut.clk)
    
    # Score should increment since press was stable
    score = dut.uio_out.value.integer
    assert score == 1, f"Score not incremented after stable press: got {score}, expected 1"

@cocotb.test()
async def test_game_timer(dut):
    """Test that the game ends after the timer expires and displays the score."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())  # Faster clock for simulation
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Score some points before timer expires
    for _ in range(3):
        idx = await wait_active(dut)
        # Press button and hold for 5 cycles to pass debouncing
        dut.ui_in.value = 1 << idx
        for _ in range(5):  # More than DEBOUNCE_CYCLES
            await RisingEdge(dut.clk)
        dut.ui_in.value = 0
        # Wait a few cycles for FSM to process the debounced press
        for _ in range(3):
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



@cocotb.test()
async def test_auto_start_on_reset(dut):
    """After reset (without pressing start), the game should auto-start and light one segment."""
    cocotb.start_soon(Clock(dut.clk, 1000, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Immediately after reset, one segment must be active (auto-start)
    await RisingEdge(dut.clk)
    seg_val = dut.uo_out.value.integer & 0x7F
    assert seg_val != 0x7F, f"Segment did not light after reset: {seg_val:07b}"


@cocotb.test()
async def test_restart_after_game_over(dut):
    """After timer expiry and GAME_OVER, pressing pb0 restarts the game."""
    cocotb.start_soon(Clock(dut.clk, 20, units='ns').start())
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Spin until the timer fires
    while not dut.game_end.value:
        await RisingEdge(dut.clk)

    # Verify GAME_OVER: wrong buttons do nothing
    active = await wait_active(dut)      # should still cycle, but no scoring
    wrong = (active + 1) % 8
    dut.ui_in.value = 1 << wrong
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Score changed in GAME_OVER"

    # Now press pb0 to restart
    dut.ui_in.value = 1 << 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0

    # And you should see a segment light again
    idx = await wait_active(dut)
    assert 0 <= idx <= 6, "No segment lit after restart"

@cocotb.test()
async def test_one_second_lockout(dut):
    """Verify that after wrong-press lockout lasts ~1s, then clears."""
    cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())  # 1 MHz
    dut.ui_in.value = 0
    await reset_dut(dut)

    # Wait for an active segment
    idx = await wait_active(dut)
    # Choose a wrong button
    wrong = (idx + 1) % 8

    # Wrong press: should lock out
    dut.ui_in.value = 1 << wrong
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Immediately attempt correct press: should NOT increment
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Lockout failed—score incremented too early"

    # Now wait for ~LOCK_CYCLES cycles plus a margin
    sim_cycles = 10 + 2   # LOCK_CYCLES in sim is 10
    for _ in range(sim_cycles):
        await RisingEdge(dut.clk)

    # After lockout expires, correct press should now increment
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

    # Pick the active segment
    idx = await wait_active(dut)
    wrong1 = (idx + 1) % 8
    wrong2 = (idx + 2) % 8

    # Press wrong1 to lock it out
    dut.ui_in.value = 1 << wrong1
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Immediately press wrong2 (should also lock it, not prevented by wrong1's lockout)
    dut.ui_in.value = 1 << wrong2
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # Both bits should be set in lockout
    # We can poke into DUT via uio_out of score is 0, but better to check that correct hit still blocked
    # Try correct hit—should still be locked
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 0, "Correct button registered during multi‐button lockout"

    # Now wait for lockout to expire
    for _ in range(12):  # 10 + margin
        await RisingEdge(dut.clk)

    # Now correct hit should work
    dut.ui_in.value = 1 << idx
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)
    assert dut.uio_out.value.integer == 1, "Multi‐button lockout did not clear"

# @cocotb.test()
# async def test_midgame_restart_resets_score_and_timer(dut):
#     """Pressing start_btn mid‐game should clear score and restart countdown."""
#     cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())
#     dut.ui_in.value = 0
#     await reset_dut(dut)

#     # Score 2 points
#     for _ in range(2):
#         idx = await wait_active(dut)
#         dut.ui_in.value = 1 << idx
#         for _ in range(5):
#             await RisingEdge(dut.clk)
#         dut.ui_in.value = 0
#         for _ in range(3):
#             await RisingEdge(dut.clk)

#     assert dut.uio_out.value.integer == 2

#     # Let timer run a bit
#     for _ in range(500):
#         await RisingEdge(dut.clk)

#     # Press pb0 to restart midgame
#     dut.ui_in.value = 1 << 0
#     for _ in range(5):
#         await RisingEdge(dut.clk)
#     dut.ui_in.value = 0
#     await RisingEdge(dut.clk)

#     # Score should be cleared
#     assert dut.uio_out.value.integer == 0

#     # Countdown should restart: game_end must go low (it was already low)
#     # But we can wait more than original target: should not end
#     for _ in range(1600):
#         await RisingEdge(dut.clk)
#     assert not dut.game_end.value, "Game ended too early after mid‐game restart"

# @cocotb.test()
# async def test_lockout_does_not_reload(dut):
#     """Ensure that while in lockout, re‐pressing the wrong button does not reset the 1s timer."""
#     cocotb.start_soon(Clock(dut.clk, 1000, 'ns').start())
#     dut.ui_in.value = 0
#     await reset_dut(dut)

#     idx = await wait_active(dut)
#     wrong = (idx + 1) % 8

#     # Trigger lockout
#     dut.ui_in.value = 1 << wrong
#     for _ in range(5):
#         await RisingEdge(dut.clk)
#     dut.ui_in.value = 0
#     await RisingEdge(dut.clk)

#     # Halfway through lockout, press wrong button again
#     for _ in range(5):
#         await RisingEdge(dut.clk)    # 5 of 10 ticks
#     dut.ui_in.value = 1 << wrong
#     for _ in range(5):
#         await RisingEdge(dut.clk)
#     dut.ui_in.value = 0
#     await RisingEdge(dut.clk)

#     # Now only ~5 ticks remain before clear; wait 6
#     for _ in range(6):
#         await RisingEdge(dut.clk)

#     # After that, correct hit should succeed
#     dut.ui_in.value = 1 << idx
#     for _ in range(5):
#         await RisingEdge(dut.clk)
#     dut.ui_in.value = 0
#     await RisingEdge(dut.clk)
#     assert dut.uio_out.value.integer == 1, "Lockout reload on repeated wrong press!"

