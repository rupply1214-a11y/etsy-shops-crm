package com.rish.smartroutine.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Update
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow

@Dao
interface ReminderDao {
    @Query("SELECT * FROM reminders ORDER BY hour, minute, id")
    fun observeAll(): Flow<List<Reminder>>

    @Query("SELECT * FROM reminders")
    suspend fun getAll(): List<Reminder>

    @Query("SELECT * FROM reminders WHERE id = :id")
    suspend fun getById(id: Long): Reminder?

    @Insert
    suspend fun insert(reminder: Reminder): Long

    @Update
    suspend fun update(reminder: Reminder)

    @Query("UPDATE reminders SET enabled = :enabled WHERE id = :id")
    suspend fun setEnabled(id: Long, enabled: Boolean)

    @Delete
    suspend fun delete(reminder: Reminder)
}

@Dao
interface CompletionDao {
    @Query("SELECT reminderId FROM completion_log WHERE epochDay = :epochDay")
    fun observeCompletedIds(epochDay: Long): Flow<List<Long>>

    @Query("SELECT EXISTS(SELECT 1 FROM completion_log WHERE reminderId = :id AND epochDay = :epochDay)")
    suspend fun isCompleted(id: Long, epochDay: Long): Boolean

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(log: CompletionLog)

    @Query("DELETE FROM completion_log WHERE reminderId = :id AND epochDay = :epochDay")
    suspend fun delete(id: Long, epochDay: Long)

    /** Housekeeping: keep ~3 months of history. */
    @Query("DELETE FROM completion_log WHERE epochDay < :beforeEpochDay")
    suspend fun prune(beforeEpochDay: Long)
}

@Dao
interface IntervalDao {
    @Query("SELECT * FROM interval_reminders ORDER BY startMinuteOfDay, id")
    fun observeAll(): Flow<List<IntervalReminder>>

    @Query("SELECT * FROM interval_reminders")
    suspend fun getAll(): List<IntervalReminder>

    @Query("SELECT COUNT(*) FROM interval_reminders")
    suspend fun count(): Int

    @Query("SELECT * FROM interval_reminders WHERE id = :id")
    suspend fun getById(id: Long): IntervalReminder?

    @Insert
    suspend fun insert(item: IntervalReminder): Long

    @Update
    suspend fun update(item: IntervalReminder)

    @Query("UPDATE interval_reminders SET enabled = :enabled WHERE id = :id")
    suspend fun setEnabled(id: Long, enabled: Boolean)

    @Delete
    suspend fun delete(item: IntervalReminder)
}

@Database(
    entities = [Reminder::class, CompletionLog::class, IntervalReminder::class],
    version = 2,
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun reminderDao(): ReminderDao
    abstract fun completionDao(): CompletionDao
    abstract fun intervalDao(): IntervalDao

    companion object {
        /** v2: course duration fields. Existing reminders become "Ongoing". */
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE reminders ADD COLUMN courseDays INTEGER")
                db.execSQL("ALTER TABLE reminders ADD COLUMN startEpochDay INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE reminders ADD COLUMN extraDays INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE reminders ADD COLUMN courseNote TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE reminders ADD COLUMN taperFromDay INTEGER")
                db.execSQL("ALTER TABLE reminders ADD COLUMN taperNote TEXT NOT NULL DEFAULT ''")
            }
        }

        @Volatile private var instance: AppDatabase? = null

        fun get(context: Context): AppDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                AppDatabase::class.java,
                "smart_routine.db",
            )
                .addMigrations(MIGRATION_1_2)
                .build().also { instance = it }
        }
    }
}
