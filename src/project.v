`default_nettype none

// Barebones RNG: 3-bit LFSR for segment selection
module rng_lfsr(
    input  wire       clk,
    input  wire       rst_n,
    output reg [2:0]  rand_seg
);
    reg [15:0] lfsr;
    wire feedback = lfsr[0] ^ lfsr[2];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= 16'hACE1;
        else
            lfsr <= {lfsr[14:0], feedback};
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rand_seg <= 3'd0;
        else
            rand_seg <= lfsr[2:0];
    end
endmodule

// Barebones 7-segment driver
module seg7_driver(
    input  wire [2:0]  segment_select,
    input  wire        game_end,
    input  wire [7:0]  score,
    output reg  [6:0]  seg,
    output reg         dp
);
    always @(*) begin
        if (!game_end) begin
            seg = 7'b1111111;
            case (segment_select)
                3'd0: seg[0] = 1'b0;
                3'd1: seg[1] = 1'b0;
                3'd2: seg[2] = 1'b0;
                3'd3: seg[3] = 1'b0;
                3'd4: seg[4] = 1'b0;
                3'd5: seg[5] = 1'b0;
                3'd6: seg[6] = 1'b0;
                default: seg[0] = 1'b0; // default to segment 0 if out-of-range
            endcase
            dp = 1'b1;
        end else begin
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
            endcase
            dp = 1'b0;
        end
    end
endmodule

// Barebones Game Control FSM
module game_fsm(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [2:0]  rand_seg,
    input  wire [7:0]  btn_sync,
    input  wire        game_end,
    output reg  [2:0]  segment_select,
    output reg  [7:0]  lockout,
    output reg  [7:0]  score_cnt
);
    typedef enum reg [0:0] { WAIT, NEXT } state_t;
    state_t state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            segment_select <= 3'd0;
            lockout        <= 8'd0;
            score_cnt      <= 8'd0;
            state          <= NEXT;
        end else if (!game_end) begin
            case (state)
                NEXT: begin
                    // Pick a new segment
                    segment_select <= (rand_seg == 3'd7) ? 3'd0 : rand_seg;
                    lockout        <= 8'd0;
                    state          <= WAIT;
                end
                WAIT: begin
                    if (btn_sync[segment_select]) begin
                        score_cnt <= score_cnt + 1;
                        state     <= NEXT;
                    end else if (|btn_sync) begin
                        lockout   <= btn_sync;
                        state     <= WAIT;
                    end
                end
            endcase
        end
    end
endmodule

// Countdown Timer Module
module countdown_timer(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    input  wire [15:0] preset,
    output reg  [15:0] count,
    output wire        done
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= preset;
        end else if (enable) begin
            if (count != 16'd0)
                count <= count - 1'b1;
            // else hold at zero
        end
    end
    assign done = (count == 16'd0);
endmodule

// Round Timer Module (same as countdown_timer, but for per-round timing)
module round_timer(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    input  wire       reset_round,
    input  wire [15:0] preset,
    output reg  [15:0] count,
    output wire        expired
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || reset_round) begin
            count <= preset;
        end else if (enable && count != 16'd0) begin
            count <= count - 1'b1;
        end
    end
    assign expired = (count == 16'd0);
endmodule

// Pattern generator: generates a random 7-bit pattern with N bits set
module pattern_gen(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] seed,
    input  wire [2:0]  num_lit,
    output reg  [6:0]  pattern
);
    // Simple LFSR-based pattern generator
    reg [15:0] lfsr;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= seed;
        else
            lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
    end
    integer i, count;
    always @(*) begin
        pattern = 7'b0;
        count = 0;
        // First pass: set bits based on LFSR
        for (i = 0; i < 7; i = i + 1) begin
            if (lfsr[i] && count < num_lit) begin
                pattern[i] = 1'b1;
                count = count + 1;
            end
        end
        // Second pass: fill remaining bits if needed
        for (i = 0; i < 7; i = i + 1) begin
            if (count < num_lit && !pattern[i]) begin
                pattern[i] = 1'b1;
                count = count + 1;
            end
        end
    end
endmodule

// Top-level: tie RNG, FSM, timer, and 7-seg driver together
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
    wire [2:0] rand_seg;
    wire [7:0] lockout;
    wire [7:0] score;
    wire [7:0] btn_sync;
    wire [15:0] timer_count;
    wire [15:0] round_timer_count;
    wire        round_expired;
    reg         reset_round;
    reg  [15:0] round_preset;
    wire [6:0]  pattern;
    reg  [2:0]  num_lit;
    wire [6:0] pattern_latched_w;
    wire [7:0] btn;
    wire [6:0] seg;
    wire dp;
    wire [7:0] led_score;
    wire game_end;
    wire effective_rst_n;
    
    // Combine reset and enable - when ena is low, effectively reset the game
    assign effective_rst_n = rst_n & ena;

    // Map Tiny Tapeout ports to game signals
    assign btn = ui_in;
    assign uo_out = {1'b0, seg};  // 7-segment display on uo_out[6:0]
    assign uio_out = led_score;    // Score on uio_out
    assign uio_oe = 8'hFF;         // All bidirectional pins as outputs

    assign btn_sync   = btn & ~lockout;
    assign led_score  = score;

    // Variable difficulty: decrease round time as score increases
    always @(*) begin
        if (score < 8'd5)
            round_preset = 16'd5000; // 5ms at 1MHz
        else if (score < 8'd10)
            round_preset = 16'd4000; // 4ms at 1MHz
        else if (score < 8'd20)
            round_preset = 16'd3000; // 3ms at 1MHz
        else
            round_preset = 16'd2000; // 2ms at 1MHz
    end
    // Variable difficulty: increase number of lit segments as score increases
    always @(*) begin
        if (score < 8'd5)
            num_lit = 3'd1;
        else if (score < 8'd10)
            num_lit = 3'd2;
        else if (score < 8'd20)
            num_lit = 3'd3;
        else
            num_lit = 3'd4;
    end

    rng_lfsr    rng_inst(
        .clk       (clk),
        .rst_n     (effective_rst_n),
        .rand_seg  (rand_seg)
    );

    pattern_gen pattern_gen_inst(
        .clk     (clk),
        .rst_n   (effective_rst_n),
        .seed    (timer_count), // Use timer as seed for variety
        .num_lit (num_lit),
        .pattern (pattern)
    );

    countdown_timer timer_inst(
        .clk    (clk),
        .rst_n  (effective_rst_n),       // Use effective reset
        .enable (ena & !game_end),       // Enable only when ena is high
        .preset (16'd60000), // 60ms at 1MHz
        .count  (timer_count),
        .done   (game_end)
    );

    round_timer round_timer_inst(
        .clk         (clk),
        .rst_n       (effective_rst_n),  // Use effective reset
        .enable      (ena & !game_end),  // Enable only when ena is high
        .reset_round (reset_round),
        .preset      (round_preset),
        .count       (round_timer_count),
        .expired     (round_expired)
    );

    // FSM with pattern and round timer integration
    game_fsm_patterns fsm_inst(
        .clk            (clk),
        .rst_n          (effective_rst_n),  // Use effective reset
        .pattern        (pattern),
        .btn_sync       (btn_sync),
        .game_end       (game_end),
        .round_expired  (round_expired),
        .reset_round    (reset_round),
        .lockout        (lockout),
        .score_cnt      (score),
        .pattern_latched(pattern_latched_w)
    );

    seg7_driver_patterns drv_inst(
        .pattern   (pattern_latched_w),
        .game_end  (game_end),
        .score     (score),
        .seg       (seg),
        .dp        (dp)
    );
endmodule

// FSM for patterns
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
    typedef enum reg [0:0] { WAIT, NEXT } state_t;
    state_t state;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pattern_latched <= 7'b0;
            lockout        <= 8'd0;
            score_cnt      <= 8'd0;
            state          <= NEXT;
            reset_round    <= 1'b1;
        end else if (!game_end) begin
            case (state)
                NEXT: begin
                    pattern_latched <= pattern;
                    lockout         <= 8'd0;
                    reset_round     <= 1'b1;
                    state           <= WAIT;
                end
                WAIT: begin
                    reset_round     <= 1'b0;
                    if ((btn_sync[6:0] & pattern_latched) == pattern_latched && pattern_latched != 7'b0) begin
                        score_cnt <= score_cnt + 1;
                        state     <= NEXT;
                    end else if (|btn_sync[6:0] & ~pattern_latched) begin
                        lockout   <= btn_sync;
                        state     <= WAIT;
                    end else if (round_expired) begin
                        state     <= NEXT;
                    end
                end
            endcase
        end
    end
endmodule

// 7-seg driver for patterns
module seg7_driver_patterns(
    input  wire [6:0]  pattern,
    input  wire        game_end,
    input  wire [7:0]  score,
    output reg  [6:0]  seg,
    output reg         dp
);
    always @(*) begin
        if (!game_end) begin
            seg = ~pattern; // active-low: light up all bits in pattern
            dp = 1'b1;
        end else begin
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
            endcase
            dp = 1'b0;
        end
    end
endmodule

`default_nettype wire