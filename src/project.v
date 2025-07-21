`default_nettype none

// ============================================================================
// Countdown Timer Module
// ============================================================================
module countdown_timer(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire [15:0] preset,
    output reg  [15:0] count,
    output wire        done
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= preset;
        else if (enable && count != 16'd0)
            count <= count - 1'b1;
    end
    assign done = (count == 16'd0);
endmodule


// ============================================================================
// Round Timer Module
// ============================================================================
module round_timer(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire        reset_round,
    input  wire [15:0] preset,
    output reg  [15:0] count,
    output wire        expired
);
    // Corrected logic for round_timer module with both async and sync reset
    always @(posedge clk or negedge rst_n) begin
        // 1. Handle the asynchronous reset first. This happens independently of the clock.
        if (!rst_n)
            count <= preset;
        // 2. All other logic is synchronous and happens only on the positive clock edge.
        else begin
            // The synchronous reset has the highest priority after the async reset.
            if (reset_round)
                count <= preset;
            // The main counter logic follows.
            else if (enable && count != 16'd0)
                count <= count - 1'b1;
        end
    end
    assign expired = (count == 16'd0);
endmodule


// ============================================================================
// Pattern Generator: LFSR-based, picks exactly num_lit bits
// ============================================================================
module pattern_gen(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] seed,
    input  wire [2:0]  num_lit,
    output reg  [6:0]  pattern
);
    reg [15:0] lfsr;
    // clocked LFSR
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= seed;
        else
            lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
    end

    integer i;
    // FIX: Changed 'integer' (32-bit) to a 3-bit reg. 'count' will never exceed 7.
    // This prevents the synthesizer from creating large, unmappable 32-bit arithmetic units.
    reg [2:0] count;

    // purely combinational pattern-pick
    always @(*) begin
        pattern = 7'b0;
        count   = 0;
        // first pass: take bits where LFSR is ‘1’
        for (i = 0; i < 7; i = i + 1) begin
            if (lfsr[i] && (count < num_lit)) begin
                pattern[i] = 1'b1;
                count      = count + 1;
            end
        end
        // second pass: fill remaining if we still need bits
        for (i = 0; i < 7; i = i + 1) begin
            if ((count < num_lit) && (pattern[i] == 1'b0)) begin
                pattern[i] = 1'b1;
                count      = count + 1;
            end
        end
    end
endmodule


// ============================================================================
// Game FSM for pattern-pressing
// ============================================================================
module game_fsm_patterns(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [6:0]  pattern,
    input  wire [7:0]  btn_sync,
    input  wire        game_end,
    input  wire        round_expired,
    output reg         reset_round,
    output reg  [7:0]  lockout,
    output reg  [7:0]  score_cnt,
    output reg  [6:0]  pattern_latched
);
    reg state;
    localparam WAIT = 1'b0;
    localparam NEXT = 1'b1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pattern_latched <= 7'b0;
            lockout         <= 8'd0;
            score_cnt       <= 8'd0;
            state           <= NEXT;
            reset_round     <= 1'b1;
        end else if (game_end) begin
            // Hold current state when game ends
            pattern_latched <= pattern_latched;
            lockout         <= lockout;
            score_cnt       <= score_cnt;
            state           <= state;
            reset_round     <= reset_round;
        end else begin
            case (state)
                NEXT: begin
                    pattern_latched <= pattern;
                    lockout         <= 8'd0;
                    reset_round     <= 1'b1;
                    state           <= WAIT;
                    score_cnt       <= score_cnt;  // Hold current score
                end
                WAIT: begin
                    reset_round <= 1'b0;
                    if ((btn_sync[6:0] & pattern_latched) == pattern_latched &&
                        (pattern_latched != 7'b0)) begin
                        // Correct pattern pressed
                        score_cnt       <= score_cnt + 1;
                        state           <= NEXT;
                        lockout         <= lockout;
                        pattern_latched <= pattern_latched;
                    end else if (|(btn_sync[6:0] & ~pattern_latched)) begin
                        // Wrong button pressed
                        lockout         <= btn_sync;
                        state           <= WAIT;
                        score_cnt       <= score_cnt;
                        pattern_latched <= pattern_latched;
                    end else if (round_expired) begin
                        // Timeout
                        state           <= NEXT;
                        lockout         <= lockout;
                        score_cnt       <= score_cnt;
                        pattern_latched <= pattern_latched;
                    end else begin
                        // Hold all values
                        state           <= WAIT;
                        lockout         <= lockout;
                        score_cnt       <= score_cnt;
                        pattern_latched <= pattern_latched;
                    end
                end
                default: begin
                    // Recover to known state
                    state           <= NEXT;
                    pattern_latched <= 7'b0;
                    lockout         <= 8'd0;
                    score_cnt       <= score_cnt;
                    reset_round     <= 1'b1;
                end
            endcase
        end
    end
endmodule


// ============================================================================
// 7-seg Driver: shows pattern or final score
// ============================================================================
module seg7_driver_patterns(
    input  wire [6:0]  pattern,
    input  wire        game_end,
    input  wire [3:0]  score,  // Changed to 4 bits since only using lower nibble
    output reg  [6:0]  seg,
    output reg         dp
);
    always @(*) begin
        // defaults
        seg = ~pattern;  // active-low for live game
        dp  = 1'b1;

        if (game_end) begin
            dp = 1'b0;
            case (score[3:0])
                4'h0: seg = 7'b1000000;
                4'h1: seg = 7'b1111001;
                4'h2: seg = 7'b0100100;
                4'h3: seg = 7'b0110000;
                4'h4: seg = 7'b0011001;
                4'h5: seg = 7'b0010010;
                4'h6: seg = 7'b0000010;
                4'h7: seg = 7'b1111000;
                4'h8: seg = 7'b0000000;
                4'h9: seg = 7'b0010000;
                4'hA: seg = 7'b0001000;
                4'hB: seg = 7'b0000011;
                4'hC: seg = 7'b1000110;
                4'hD: seg = 7'b0100001;
                4'hE: seg = 7'b0000110;
                4'hF: seg = 7'b0001110;
                default: seg = 7'b1000000;
            endcase
        end
    end
endmodule


// ============================================================================
// Top-Level: Tie everything together
// ============================================================================
module tt_um_whack_a_mole(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        ena,
    input  wire [7:0]  ui_in,
    output wire [7:0]  uo_out,
    input  wire [7:0]  uio_in,
    output wire [7:0]  uio_out,
    output wire [7:0]  uio_oe
);
    // ------------------------------------------------------------------------
    // Wires & regs
    // ------------------------------------------------------------------------
    // FIX: 'lockout' must be a wire, as it is driven by an instance output (fsm_inst).
    // It cannot be a 'reg' in this module.
    wire [7:0] lockout;
    wire [7:0] btn_sync        = ui_in & ~lockout;
    wire [7:0] score;
    wire       game_end;
    wire [15:0] timer_count;
    // FIX: Removed unused 'timer_round' wire to clear the linting warning.
    wire       round_expired;
    wire       reset_round;
    wire [6:0] pattern_latched;
    wire [6:0] next_pattern;
    wire _unused_ok = &{1'b0, uio_in};  // Explicitly mark unused input

    // make these pure combinational (no latches)
    wire [15:0] round_preset = (score < 8'd5)  ? 16'd5000 :
                               (score < 8'd10) ? 16'd4000 :
                               (score < 8'd20) ? 16'd3000 :
                                                 16'd2000;

    wire [2:0]  num_lit      = (score < 8'd5)  ? 3'd1 :
                               (score < 8'd10) ? 3'd2 :
                               (score < 8'd20) ? 3'd3 :
                                                 3'd4;

    wire [6:0] seg;
    wire       dp;

    // display connections
    assign uo_out  = {dp, seg};
    assign uio_out = score;
    assign uio_oe  = 8'hFF;


    // ------------------------------------------------------------------------
    // Instantiations
    // ------------------------------------------------------------------------
    // main game-end timer
    countdown_timer timer_inst (
        .clk    (clk),
        .rst_n  (rst_n & ena),
        .enable (ena && !game_end),
        .preset (16'd60000),
        .count  (timer_count),
        .done   (game_end)
    );

    // per-round timeout
    wire [15:0] unused_round_count; // Dummy wire for unused output
    round_timer round_timer_inst (
        .clk         (clk),
        .rst_n       (rst_n & ena),
        .enable      (ena && !game_end),
        .reset_round (reset_round),
        .preset      (round_preset),
        .count       (unused_round_count), // Connect unused output
        .expired     (round_expired)
    );

    // pattern bit-generator
    pattern_gen pattern_gen_inst (
        .clk     (clk),
        .rst_n   (rst_n & ena),
        .seed    (timer_count),
        .num_lit (num_lit),
        .pattern (next_pattern)
    );

    // main FSM: latches the pattern, tracks score & lockout
    game_fsm_patterns fsm_inst (
        .clk            (clk),
        .rst_n          (rst_n & ena),
        .pattern        (next_pattern),
        .btn_sync       (btn_sync),
        .game_end       (game_end),
        .round_expired  (round_expired),
        .reset_round    (reset_round),
        .lockout        (lockout),
        .score_cnt      (score),
        .pattern_latched(pattern_latched)
    );

    // 7-segment output driver
    seg7_driver_patterns drv_inst (
        .pattern  (pattern_latched),
        .game_end (game_end),
        .score    (score[3:0]),  // Only pass lower 4 bits
        .seg      (seg),
        .dp       (dp)
    );
endmodule

`default_nettype wire
