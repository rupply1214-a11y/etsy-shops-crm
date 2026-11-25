# Room entities/DAOs are handled by Room's own consumer rules.
# Keep enum names because they are stored as strings in the database.
-keepclassmembers enum com.rish.smartroutine.data.** { *; }
