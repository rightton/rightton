# Reference houses

These are NREL's OpenStudio-HPXML sample houses (`workflow/sample_files/*.xml`,
commit fb18723), after the reference engine filled in its defaults (`in.xml`),
gzipped. They are synthetic test buildings, not real homes. BSD-style license:
see `core/NOTICE-OpenStudio-HPXML.md`.

Only one house is kept per distinct set of reference design loads; sample files
that differ only in appliances, schedules or equipment efficiency give the same
loads and are left out. `validation/compare.py --snapshot` regenerates this folder.
