"""One module per law family (issue #857).  Each carries its check
function(s) and ``LAW_FAMILY_ROWS`` — its ``(key, title, bucket)`` rows
of ``check_grade.LAW_FAMILIES``, which splices them in at the family's
emission position so the register's ORDER is unchanged."""
