`default_nettype none

// Enhanced RNG: Multiple LFSRs with external entropy for true randomness
module enhanced_rng(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] btn,
    input  wire [15:0] timer_count,
    output reg [2:0]  rand_seg
);
    // Multiple LFSRs for better randomness
    reg [15:0] lfsr1, lfsr2;
    reg [7:0]  entropy_reg;
    reg [23:0] combined_state;
    
    // Maximal-length LFSR feedback polynomials
    wire feedback1 = lfsr1[15] ^ lfsr1[14] ^ lfsr1[13] ^ lfsr1[4];  // 16-bit maximal
    wire feedback2 = lfsr2[15] ^ lfsr2[13] ^ lfsr2[12] ^ lfsr2[10];  // Different taps
    
    // External entropy from button presses and timer
    wire [15:0] external_entropy = {btn, timer_count[7:0]};
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr1 <= 16'hACE1;
            lfsr2 <= 16'hBEEF;
            entropy_reg <= 8'h00;
            combined_state <= 24'h0;
        end else begin
            // Update LFSRs
            lfsr1 <= {lfsr1[14:0], feedback1};
            lfsr2 <= {lfsr2[14:0], feedback2};
            
            // Collect external entropy
            entropy_reg <= entropy_reg ^ btn;
            
            // Combine all sources for final random number
            combined_state <= {lfsr1[7:0], lfsr2[7:0], entropy_reg} ^ {external_entropy, 8'h0};
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rand_seg <= 3'd0;
        else
            // Ensure we get a valid segment (0-6)
            rand_seg <= combined_state[2:0] % 7;
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

// Enhanced pattern generator: truly random patterns with multiple entropy sources
module enhanced_pattern_gen(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  btn,
    input  wire [15:0] timer_count,
    input  wire [2:0]  num_lit,
    output reg  [6:0]  pattern
);
    // Multiple entropy sources for true randomness
    reg [15:0] lfsr1, lfsr2;
    reg [7:0]  entropy_reg;
    reg [23:0] combined_entropy;
    reg [6:0]  random_bits;
    
    // Different maximal-length LFSR configurations
    wire feedback1 = lfsr1[15] ^ lfsr1[14] ^ lfsr1[13] ^ lfsr1[4];
    wire feedback2 = lfsr2[15] ^ lfsr2[13] ^ lfsr2[12] ^ lfsr2[10];
    
    // External entropy sources
    wire [15:0] external_entropy = {btn, timer_count[7:0]};
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr1 <= 16'hFACE;
            lfsr2 <= 16'hCAFE;
            entropy_reg <= 8'h00;
            combined_entropy <= 24'h0;
            random_bits <= 7'h0;
        end else begin
            // Update LFSRs
            lfsr1 <= {lfsr1[14:0], feedback1};
            lfsr2 <= {lfsr2[14:0], feedback2};
            
            // Collect external entropy
            entropy_reg <= entropy_reg ^ btn;
            
            // Combine all entropy sources
            combined_entropy <= {lfsr1[7:0], lfsr2[7:0], entropy_reg} ^ {external_entropy, 8'h0};
            
            // Generate random bits for pattern
            random_bits <= combined_entropy[6:0] ^ {combined_entropy[15:9]};
        end
    end
    
    integer i, count;
    always @(*) begin
        pattern = 7'b0;
        count = 0;
        
        // Use random bits to set exactly num_lit bits
        for (i = 0; i < 7 && count < num_lit; i = i + 1) begin
            if (random_bits[i] || (count < num_lit && i >= 6)) begin
                pattern[i] = 1'b1;
                count = count + 1;
            end
        end
        
        // Ensure we have exactly num_lit bits set
        if (count < num_lit) begin
            for (i = 0; i < 7 && count < num_lit; i = i + 1) begin
                if (!pattern[i]) begin
                    pattern[i] = 1'b1;
                    count = count + 1;
                end
            end
        end
    end
endmodule

// Top-level: tie RNG, FSM, timer, and 7-seg driver together
module whack_a_mole(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  btn,
    output wire [6:0]  seg,
    output wire        dp,
    output wire [7:0]  led_score,
    output wire        game_end,
    output wire [6:0]  pattern_latched
);
    wire [2:0] rand_seg;
    wire [2:0] segment_select;
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

    enhanced_rng    rng_inst(
        .clk         (clk),
        .rst_n       (rst_n),
        .btn         (btn),
        .timer_count (timer_count),
        .rand_seg    (rand_seg)
    );

    enhanced_pattern_gen pattern_gen_inst(
        .clk         (clk),
        .rst_n       (rst_n),
        .btn         (btn),
        .timer_count (timer_count),
        .num_lit     (num_lit),
        .pattern     (pattern)
    );

    countdown_timer timer_inst(
        .clk    (clk),
        .rst_n  (rst_n),
        .enable (!game_end),
        .preset (16'd60000), // 60ms at 1MHz
        .count  (timer_count),
        .done   (game_end)
    );

    round_timer round_timer_inst(
        .clk         (clk),
        .rst_n       (rst_n),
        .enable      (!game_end),
        .reset_round (reset_round),
        .preset      (round_preset),
        .count       (round_timer_count),
        .expired     (round_expired)
    );

    // FSM with pattern and round timer integration
    game_fsm_patterns fsm_inst(
        .clk            (clk),
        .rst_n          (rst_n),
        .pattern        (pattern),
        .btn_sync       (btn_sync),
        .game_end       (game_end),
        .round_expired  (round_expired),
        .reset_round    (reset_round),
        .lockout        (lockout),
        .score_cnt      (score),
        .pattern_latched(pattern_latched_w)
    );

    assign pattern_latched = pattern_latched_w;

    seg7_driver_patterns drv_inst(
        .pattern   (pattern),
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
                    end else if (|(btn_sync[6:0] & ~pattern_latched)) begin
                        lockout   <= lockout | btn_sync;
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
