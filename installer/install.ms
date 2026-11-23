-- Backdrop a0.004 -- installer
-- 1) Copies backdrop.py into <userscripts>\python (a directory searched by
--    python.ExecuteFile, per Autodesk docs "Executing Python from MAXScript").
-- 2) Copies the multi-resolution PNG icons into <usericons>\Dark|Light.
-- 3) Defines a macroScript; evaluating the definition (re)writes
--    "AD Tools-Backdrop.mcr" in the usermacros folder, per Autodesk docs
--    "Defining Macro Scripts".
(
    local srcDir  = getFilenamePath (getThisScriptFilename())
    local srcFile = srcDir + "backdrop.py"
    -- Run straight from the repository: the script sits in ..\src.
    if not (doesFileExist srcFile) do srcFile = srcDir + "..\\src\\backdrop.py"

    local pyDir = (getDir #userScripts) + "\\python"
    if not (doesFileExist pyDir) do makeDir pyDir all:true

    local dstFile = pyDir + "\\backdrop.py"
    if doesFileExist dstFile do deleteFile dstFile

    -- Toolbar icons: 3ds Max finds them by iconName in <usericons>\Dark|Light.
    for theme in #("Dark", "Light") do
    (
        local dstIconDir = (getDir #userIcons) + "\\" + theme
        if not (doesFileExist dstIconDir) do makeDir dstIconDir all:true
        for sz in #(24, 30, 36, 48) do
        (
            local iconFile = "Backdrop_" + (sz as string) + ".png"
            local srcIcon  = srcDir + "icons\\" + theme + "\\" + iconFile
            local dstIcon  = dstIconDir + "\\" + iconFile
            if doesFileExist srcIcon do
            (
                if doesFileExist dstIcon do deleteFile dstIcon
                copyFile srcIcon dstIcon
            )
        )
    )

    if (copyFile srcFile dstFile) then
    (
        macroScript Backdrop
        category:"AD Tools"
        toolTip:"Backdrop (Python)"
        buttonText:"Backdrop"
        iconName:"Backdrop"
        (
            python.ExecuteFile ((getDir #userScripts) + "\\python\\backdrop.py")
        )

        messageBox ("Backdrop a0.004 installed.\n\n" +
                    "Script copied to:\n" + dstFile + "\n\n" +
                    "Customize > Customize User Interface > Toolbars,\n" +
                    "Category: \"AD Tools\", drag \"Backdrop\" onto a toolbar.") \
                   title:"Backdrop"
    )
    else
        messageBox ("Install FAILED: could not copy\n" + srcFile + "\nto\n" + dstFile) \
                   title:"Backdrop"
)
