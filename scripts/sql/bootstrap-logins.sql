:ON ERROR EXIT
SET NOCOUNT ON;
DECLARE @DatabaseName sysname = N'$(DatabaseName)';
DECLARE @AppLogin sysname = N'$(AppLogin)';
DECLARE @AppPassword nvarchar(128) = N'$(AppPassword)';
DECLARE @MigrationLogin sysname = N'$(MigrationLogin)';
DECLARE @MigrationPassword nvarchar(128) = N'$(MigrationPassword)';
DECLARE @Sql nvarchar(max);
IF @DatabaseName = N'' OR @AppLogin = N'' OR @MigrationLogin = N''
    THROW 51100, 'Database and login names are required.', 1;
IF @AppLogin = @MigrationLogin
    THROW 51101, 'Runtime and migration logins must be different.', 1;
IF DB_ID(@DatabaseName) IS NULL
BEGIN
    SET @Sql = N'CREATE DATABASE ' + QUOTENAME(@DatabaseName) + N';';
    EXEC (@Sql);
END;
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = @AppLogin)
BEGIN
    SET @Sql = N'CREATE LOGIN ' + QUOTENAME(@AppLogin) +
        N' WITH PASSWORD = ' + QUOTENAME(@AppPassword, N'''') +
        N', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;';
    EXEC (@Sql);
END
ELSE
BEGIN
    SET @Sql = N'ALTER LOGIN ' + QUOTENAME(@AppLogin) +
        N' WITH PASSWORD = ' + QUOTENAME(@AppPassword, N'''') + N';';
    EXEC (@Sql);
END;
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = @MigrationLogin)
BEGIN
    SET @Sql = N'CREATE LOGIN ' + QUOTENAME(@MigrationLogin) +
        N' WITH PASSWORD = ' + QUOTENAME(@MigrationPassword, N'''') +
        N', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;';
    EXEC (@Sql);
END
ELSE
BEGIN
    SET @Sql = N'ALTER LOGIN ' + QUOTENAME(@MigrationLogin) +
        N' WITH PASSWORD = ' + QUOTENAME(@MigrationPassword, N'''') + N';';
    EXEC (@Sql);
END;
SET @Sql = N'USE ' + QUOTENAME(@DatabaseName) + N';
IF DATABASE_PRINCIPAL_ID(N' + QUOTENAME(@AppLogin, N'''') + N') IS NULL
    CREATE USER ' + QUOTENAME(@AppLogin) + N' FOR LOGIN ' + QUOTENAME(@AppLogin) + N';
IF DATABASE_PRINCIPAL_ID(N' + QUOTENAME(@MigrationLogin, N'''') + N') IS NULL
    CREATE USER ' + QUOTENAME(@MigrationLogin) + N' FOR LOGIN ' + QUOTENAME(@MigrationLogin) + N';
IF DATABASE_PRINCIPAL_ID(N''retailo_runtime_executor'') IS NULL
    CREATE ROLE [retailo_runtime_executor];
IF NOT EXISTS (SELECT 1 FROM sys.database_role_members WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N''db_datareader'') AND member_principal_id = DATABASE_PRINCIPAL_ID(N' + QUOTENAME(@AppLogin, N'''') + N'))
    ALTER ROLE [db_datareader] ADD MEMBER ' + QUOTENAME(@AppLogin) + N';
IF NOT EXISTS (SELECT 1 FROM sys.database_role_members WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N''db_datawriter'') AND member_principal_id = DATABASE_PRINCIPAL_ID(N' + QUOTENAME(@AppLogin, N'''') + N'))
    ALTER ROLE [db_datawriter] ADD MEMBER ' + QUOTENAME(@AppLogin) + N';
IF NOT EXISTS (SELECT 1 FROM sys.database_role_members WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N''retailo_runtime_executor'') AND member_principal_id = DATABASE_PRINCIPAL_ID(N' + QUOTENAME(@AppLogin, N'''') + N'))
    ALTER ROLE [retailo_runtime_executor] ADD MEMBER ' + QUOTENAME(@AppLogin) + N';
GRANT EXECUTE ON SCHEMA::[dbo] TO [retailo_runtime_executor];
IF NOT EXISTS (SELECT 1 FROM sys.database_role_members WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N''db_owner'') AND member_principal_id = DATABASE_PRINCIPAL_ID(N' + QUOTENAME(@MigrationLogin, N'''') + N'))
    ALTER ROLE [db_owner] ADD MEMBER ' + QUOTENAME(@MigrationLogin) + N';';
EXEC (@Sql);
PRINT N'Retailo SQL logins configured.';
