create_clock -period 5.000 -name chia_rdo_clk [get_ports clk]
set_false_path -from [get_ports rst_n]
