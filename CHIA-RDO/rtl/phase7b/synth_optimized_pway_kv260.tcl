set parallelism [lindex $argv 0]
set output_dir [file normalize [lindex $argv 1]]
set pipeline_depth [expr {[llength $argv] > 2 ? [lindex $argv 2] : 2}]
set cost_width [expr {[llength $argv] > 3 ? [lindex $argv 3] : 56}]
set max_candidates [expr {[llength $argv] > 4 ? [lindex $argv 4] : 35}]
file mkdir $output_dir

read_verilog -sv rtl/rdo_pe.sv rtl/phase7b/full_rdo_mvp_4x4_serial.sv \
  rtl/phase7b/full_rdo_pway_optimized.sv
read_xdc rtl/constraints/kv260.xdc
synth_design -top full_rdo_pway_optimized -part xck26-sfvc784-2LV-c \
  -mode out_of_context -generic "P=$parallelism PIPELINE_DEPTH=$pipeline_depth COST_WIDTH=$cost_width MAX_CANDIDATES=$max_candidates"
report_utilization -file $output_dir/utilization_synth.rpt
report_utilization -hierarchical -hierarchical_depth 8 \
  -file $output_dir/utilization_synth_hierarchical.rpt
write_checkpoint -force $output_dir/post_synth.dcp

opt_design
place_design
report_utilization -file $output_dir/utilization_place.rpt
report_timing_summary -delay_type max -max_paths 10 -file $output_dir/timing_place.rpt

phys_opt_design
route_design
report_utilization -file $output_dir/utilization_route.rpt
report_utilization -hierarchical -hierarchical_depth 8 \
  -file $output_dir/utilization_route_hierarchical.rpt
report_timing_summary -delay_type max -max_paths 10 -file $output_dir/timing_summary.rpt
report_timing -delay_type max -max_paths 10 -path_type full_clock_expanded \
  -file $output_dir/timing_paths_detailed.rpt
report_power -file $output_dir/power.rpt
write_checkpoint -force $output_dir/full_rdo_pway_optimized_routed.dcp
