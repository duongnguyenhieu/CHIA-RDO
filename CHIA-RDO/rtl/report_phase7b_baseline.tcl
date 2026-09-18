set checkpoint [file normalize [lindex $argv 0]]
set output_dir [file normalize [lindex $argv 1]]
file mkdir $output_dir

open_checkpoint $checkpoint
report_utilization -hierarchical -hierarchical_depth 8 -file $output_dir/utilization_hierarchical.rpt
set dsp_file [open $output_dir/dsp_cells.rpt w]
puts $dsp_file "NAME|PARENT|REF_NAME|ORIG_REF_NAME"
foreach cell [lsort [get_cells -hierarchical -filter {REF_NAME == DSP48E2}]] {
  puts $dsp_file "[get_property NAME $cell]|[get_property PARENT $cell]|[get_property REF_NAME $cell]|[get_property ORIG_REF_NAME $cell]"
}
close $dsp_file
report_timing -delay_type max -max_paths 10 -path_type full_clock_expanded \
  -file $output_dir/timing_paths_detailed.rpt
close_design
