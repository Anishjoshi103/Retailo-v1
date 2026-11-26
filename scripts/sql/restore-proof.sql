:ON ERROR EXIT
SET NOCOUNT ON;
DECLARE @BackupPath nvarchar(4000) = N'$(BackupFile)';
DECLARE @RestoreDatabase sysname = N'$(RestoreDb)';
DECLARE @FileListSql nvarchar(max);
DECLARE @MoveClause nvarchar(max);
DECLARE @RestoreSql nvarchar(max);

IF DB_ID(@RestoreDatabase) IS NOT NULL
    THROW 51000, 'Restore proof database already exists; refusing to overwrite it.', 1;

CREATE TABLE #BackupFiles
(
    LogicalName nvarchar(128),
    PhysicalName nvarchar(260),
    [Type] char(1),
    FileGroupName nvarchar(128) NULL,
    [Size] numeric(20,0),
    MaxSize numeric(20,0),
    FileId bigint,
    CreateLSN numeric(25,0),
    DropLSN numeric(25,0),
    UniqueId uniqueidentifier,
    ReadOnlyLSN numeric(25,0),
    ReadWriteLSN numeric(25,0),
    BackupSizeInBytes bigint,
    SourceBlockSize int,
    FileGroupId int,
    LogGroupGUID uniqueidentifier NULL,
    DifferentialBaseLSN numeric(25,0),
    DifferentialBaseGUID uniqueidentifier,
    IsReadOnly bit,
    IsPresent bit,
    TDEThumbprint varbinary(32) NULL,
    SnapshotURL nvarchar(360) NULL
);

SET @FileListSql = N'RESTORE FILELISTONLY FROM DISK = N''' + REPLACE(@BackupPath, N'''', N'''''') + N'''';
INSERT INTO #BackupFiles EXEC (@FileListSql);

IF NOT EXISTS (SELECT 1 FROM #BackupFiles WHERE [Type] = 'D')
    THROW 51001, 'Backup contains no data files.', 1;
IF NOT EXISTS (SELECT 1 FROM #BackupFiles WHERE [Type] = 'L')
    THROW 51002, 'Backup contains no log files.', 1;
IF EXISTS (SELECT 1 FROM #BackupFiles WHERE [Type] NOT IN ('D', 'L'))
    THROW 51003, 'Backup contains FILESTREAM or unsupported file types; use the documented manual restore drill.', 1;

SELECT @MoveClause = STRING_AGG(
    CAST(
        N'MOVE ' + QUOTENAME(LogicalName, N'''') + N' TO ' +
        QUOTENAME(
            N'/var/opt/mssql/data/' + @RestoreDatabase + N'_' +
            CONVERT(nvarchar(20), FileId) +
            CASE WHEN [Type] = 'L' THEN N'.ldf'
                 WHEN FileId = 1 THEN N'.mdf'
                 ELSE N'.ndf' END,
            N''''
        )
        AS nvarchar(max)
    ),
    N', '
) WITHIN GROUP (ORDER BY FileId)
FROM #BackupFiles;

SET @RestoreSql =
    N'RESTORE DATABASE ' + QUOTENAME(@RestoreDatabase) +
    N' FROM DISK = N''' + REPLACE(@BackupPath, N'''', N'''''') +
    N''' WITH ' + @MoveClause + N', RECOVERY, CHECKSUM, STATS = 10;';
EXEC sys.sp_executesql @RestoreSql;

DECLARE @CheckSql nvarchar(max) =
    N'DBCC CHECKDB (' + QUOTENAME(@RestoreDatabase, N'''') +
    N') WITH NO_INFOMSGS, ALL_ERRORMSGS;';
EXEC sys.sp_executesql @CheckSql;

DECLARE @DropSql nvarchar(max) =
    N'ALTER DATABASE ' + QUOTENAME(@RestoreDatabase) +
    N' SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE ' +
    QUOTENAME(@RestoreDatabase) + N';';
EXEC sys.sp_executesql @DropSql;

SELECT N'RESTORE_PROOF_OK' AS result, @BackupPath AS backupFile;
