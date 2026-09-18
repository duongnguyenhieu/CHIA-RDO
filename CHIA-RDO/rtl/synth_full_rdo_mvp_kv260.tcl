set output_dir [file normalize [lindex $argv 0]]
file mkdir $output_dir

read_verilog -sv rtl/rdo_pe.sv rtl/full_rdo_codec_4x4.sv rtl/full_rdo_mvp_4x4.sv
read_xdc rtl/constraints/kv260.xdc
synth_design -top full_rdo_mvp_4x4 -part xck26-sfvc784-2LV-c -mode out_of_context
opt_design
place_design
phys_opt_design
route_design

report_utilization -file $output_dir/utilization.rpt
report_timing_summary -delay_type max -max_paths 10 -file $output_dir/timing_summary.rpt
report_power -file $output_dir/power.rpt
report_methodology -file $output_dir/methodology.rpt
write_checkpoint -force $output_dir/full_rdo_mvp_4x4_routed.dcp

set timing_path [get_timing_paths -delay_type max -max_paths 1]
set slack [get_property SLACK $timing_path]
set metrics [open $output_dir/metrics.txt w]
puts $metrics "lut=[llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]"
puts $metrics "ff=[llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]"
puts $metrics "bram=[llength [get_cells -hierarchical -filter {REF_NAME =~ RAMB*}]]"
puts $metrics "dsp=[llength [get_cells -hierarchical -filter {REF_NAME =~ DSP*}]]"
puts $metrics "wns_ns=$slack"
puts $metrics "fmax_mhz=[expr {1000.0 / (5.0 - $slack)}]"
close $metrics
