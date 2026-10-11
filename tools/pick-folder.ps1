param(
    [string]$InitialDirectory = "",
    [switch]$ValidateOnly
)

$source = @'
using System;
using System.Runtime.InteropServices;

public static class KlipeFolderPicker {
    [ComImport, Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]
    private class FileOpenDialog { }

    [ComImport, Guid("D57C7288-D4AD-4768-BE02-9D969532D960"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileOpenDialog {
        [PreserveSig] uint Show(IntPtr parent);
        void SetFileTypes(uint count, IntPtr specs);
        void SetFileTypeIndex(uint index);
        void GetFileTypeIndex(out uint index);
        void Advise(IntPtr events, out uint cookie);
        void Unadvise(uint cookie);
        void SetOptions(uint options);
        void GetOptions(out uint options);
        void SetDefaultFolder(IShellItem item);
        void SetFolder(IShellItem item);
        void GetFolder(out IShellItem item);
        void GetCurrentSelection(out IShellItem item);
        void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string name);
        void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string name);
        void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string title);
        void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string text);
        void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string label);
        void GetResult(out IShellItem item);
        void AddPlace(IShellItem item, int alignment);
        void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string extension);
        void Close(int result);
        void SetClientGuid(ref Guid guid);
        void ClearClientData();
        void SetFilter(IntPtr filter);
        void GetResults(IntPtr items);
        void GetSelectedItems(IntPtr items);
    }

    [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellItem {
        void BindToHandler(IntPtr bindContext, ref Guid handler, ref Guid iid, out IntPtr result);
        void GetParent(out IShellItem parent);
        void GetDisplayName(uint nameType, out IntPtr name);
        void GetAttributes(uint mask, out uint attributes);
        void Compare(IShellItem other, uint hint, out int order);
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    private static extern void SHCreateItemFromParsingName(
        string path, IntPtr bindContext, ref Guid iid, out IShellItem item);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    public static string Pick(string initialDirectory) {
        IFileOpenDialog dialog = (IFileOpenDialog)new FileOpenDialog();
        IShellItem initial = null;
        IShellItem result = null;
        try {
            uint options;
            dialog.GetOptions(out options);
            dialog.SetOptions(options | 0x20u | 0x40u | 0x800u);
            dialog.SetTitle("Onde salvar o vídeo");
            dialog.SetOkButtonLabel("Selecionar pasta");

            if (!String.IsNullOrWhiteSpace(initialDirectory)) {
                Guid shellItemId = new Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE");
                try {
                    SHCreateItemFromParsingName(initialDirectory, IntPtr.Zero, ref shellItemId, out initial);
                    dialog.SetFolder(initial);
                } catch { }
            }

            uint shown = dialog.Show(GetForegroundWindow());
            if (shown != 0) return null;
            dialog.GetResult(out result);
            IntPtr raw;
            result.GetDisplayName(0x80058000u, out raw);
            try { return Marshal.PtrToStringUni(raw); }
            finally { Marshal.FreeCoTaskMem(raw); }
        } finally {
            if (result != null) Marshal.FinalReleaseComObject(result);
            if (initial != null) Marshal.FinalReleaseComObject(initial);
            Marshal.FinalReleaseComObject(dialog);
        }
    }
}
'@

Add-Type -TypeDefinition $source -Language CSharp
if ($ValidateOnly) { exit 0 }
$selected = [KlipeFolderPicker]::Pick($InitialDirectory)
if ($selected) { [Console]::Out.WriteLine($selected) }
