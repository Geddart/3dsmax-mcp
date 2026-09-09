# Original process-scoped UIA helper. Input is JSON data on stdin, never code.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing, System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class MaxWindowApi {
 public delegate bool EnumProc(IntPtr hwnd, IntPtr data);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc fn, IntPtr data);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, string text, uint flags, uint timeout, out IntPtr result);
 [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageTimeoutW")] public static extern IntPtr ReadText(IntPtr h, uint msg, IntPtr w, StringBuilder text, uint flags, uint timeout, out IntPtr result);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder text, int count);
 [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int index);
 [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] static extern bool AttachThreadInput(uint from, uint to, bool attach);
 [DllImport("user32.dll")] static extern IntPtr SetFocus(IntPtr h);
 [StructLayout(LayoutKind.Sequential)] struct Rect { public int left, top, right, bottom; }
 [StructLayout(LayoutKind.Sequential)] struct GuiThreadInfo {
  public uint size, flags;
  public IntPtr active, focus, capture, menuOwner, moveSize, caret;
  public Rect caretRect;
 }
 [DllImport("user32.dll")] static extern bool GetGUIThreadInfo(uint thread, ref GuiThreadInfo info);
 public static bool HasNativeFocus(IntPtr h) {
  uint pid; uint thread=GetWindowThreadProcessId(h,out pid);
  var info=new GuiThreadInfo(); info.size=(uint)Marshal.SizeOf(typeof(GuiThreadInfo));
  return GetGUIThreadInfo(thread,ref info) && info.focus==h;
 }
 public static bool FocusNative(IntPtr h) {
  uint pid; uint target=GetWindowThreadProcessId(h,out pid), current=GetCurrentThreadId();
  if (target==0 || !AttachThreadInput(current,target,true)) return false;
  try { SetFocus(h); }
  finally { AttachThreadInput(current,target,false); }
  return HasNativeFocus(h);
 }
}
'@
$targetProcess = Get-Process -Id ([int]$request.process_id)
if ($targetProcess.ProcessName -ne '3dsmax') { throw 'Target must be 3dsmax.exe' }
$birth = $targetProcess.StartTime.ToUniversalTime().Ticks.ToString()
$targetId = $targetProcess.Id
$ae = [System.Windows.Automation.AutomationElement]
$walker = [System.Windows.Automation.TreeWalker]::RawViewWalker

function Assert-Owner($element) {
 if ($element.Current.ProcessId -ne $targetId) { throw 'Control belongs to another process' }
 if ((Get-Process -Id $targetId).StartTime.ToUniversalTime().Ticks.ToString() -ne $birth) { throw 'Process changed' }
}
function Root-From-Token($token) {
 if ($null -eq $token -or $token.pid -ne $targetId -or $token.birth -ne $birth) { throw 'Stale or foreign process token' }
 $root = $ae::FromHandle([IntPtr]([long]$token.hwnd))
 Assert-Owner $root
 if (($root.GetRuntimeId() -join '.') -ne $token.root_id) { throw 'Stale window token; list windows again' }
 return $root
}
function Token($element, $root, $hwnd) {
 return @{pid=$targetId;birth=$birth;hwnd=$hwnd.ToString();root_id=($root.GetRuntimeId() -join '.');runtime_id=($element.GetRuntimeId() -join '.')}
}
function Describe($element, $root, $hwnd, $depth) {
 Assert-Owner $element
 $current = $element.Current
 $patterns = @($element.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName })
 return @{token=(Token $element $root $hwnd);name=$current.Name;automation_id=$current.AutomationId;
          class_name=$current.ClassName;control_type=$current.ControlType.ProgrammaticName;
          enabled=$current.IsEnabled;offscreen=$current.IsOffscreen;password=$current.IsPassword;
          patterns=$patterns;depth=$depth;native_handle=$current.NativeWindowHandle;
          native_set_value=($current.ClassName -eq 'Edit');native_invoke=($current.ClassName -in 'Button','CustButton')}
}
function Resolve-Control($token) {
 $root = Root-From-Token $token
 $queue = [Collections.Generic.Queue[object]]::new()
 $queue.Enqueue($root)
 $count = 0
 while ($queue.Count -and $count -lt 3000) {
  $element = $queue.Dequeue(); $count++
  Assert-Owner $element
  if (($element.GetRuntimeId() -join '.') -eq $token.runtime_id) { return $element }
  $child = $walker.GetFirstChild($element)
  while ($null -ne $child -and ($count + $queue.Count) -lt 3000) {
   if ($child.Current.ProcessId -eq $targetId) { $queue.Enqueue($child) }
   $child = $walker.GetNextSibling($child)
  }
 }
 throw 'Control no longer exists or exceeds search bound; inspect again'
}

switch ($request.action) {
 'windows' {
  $handles = [Collections.Generic.List[IntPtr]]::new()
  $callback = [MaxWindowApi+EnumProc]{ param($h,$data)
   [uint32]$owner = 0
   [void][MaxWindowApi]::GetWindowThreadProcessId($h,[ref]$owner)
   if ($owner -eq $targetId -and [MaxWindowApi]::IsWindowVisible($h)) { $handles.Add($h) }
   return $true
  }
  [void][MaxWindowApi]::EnumWindows($callback,[IntPtr]::Zero)
  $found = @($handles | ForEach-Object {
   $root = $ae::FromHandle($_); Assert-Owner $root
   @{title=$root.Current.Name;token=(Token $root $root $_)}
  })
  @{windows=$found} | ConvertTo-Json -Depth 12 -Compress
 }
 'inspect' {
  $root = Root-From-Token $request.window
  $truncated=$false
  $rows = [Collections.Generic.List[object]]::new()
  $queue = [Collections.Generic.Queue[object]]::new(); $queue.Enqueue(@($root,0))
  while ($queue.Count -and $rows.Count -lt $request.max_elements) {
   $entry=$queue.Dequeue(); $element=$entry[0]; $depth=$entry[1]
   $rows.Add((Describe $element $root $request.window.hwnd $depth))
   if ($depth -lt $request.max_depth) {
    $child=$walker.GetFirstChild($element)
    while ($null -ne $child -and $queue.Count -lt 1000) {
     if ($child.Current.ProcessId -eq $targetId) { $queue.Enqueue(@($child,($depth+1))) }
     $child=$walker.GetNextSibling($child)
    }
    if ($null -ne $child) { $truncated=$true }
   } elseif ($null -ne $walker.GetFirstChild($element)) {
    $truncated=$true
   }
  }
  @{elements=@($rows.ToArray());truncated=($truncated -or $queue.Count -gt 0)} | ConvertTo-Json -Depth 12 -Compress
 }
 'capture' {
  $root=Root-From-Token $request.window; $bounds=$root.Current.BoundingRectangle
  if ($bounds.Width -le 0 -or $bounds.Height -le 0 -or $bounds.Width*$bounds.Height -gt 32000000) { throw 'Invalid capture dimensions' }
  $bitmap=[Drawing.Bitmap]::new([int]$bounds.Width,[int]$bounds.Height)
  $graphics=[Drawing.Graphics]::FromImage($bitmap); $dc=$graphics.GetHdc()
  try { $ok=[MaxWindowApi]::PrintWindow([IntPtr]([long]$request.window.hwnd),$dc,2) }
  finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
  try {
   if (-not $ok) { throw 'PrintWindow failed; this window may not support capture' }
   $bitmap.Save($request.output_path,[Drawing.Imaging.ImageFormat]::Png)
  } finally { $bitmap.Dispose() }
  @{file=$request.output_path;mime_type='image/png'} | ConvertTo-Json -Compress
 }
 { $_ -in 'invoke','set_value','send_keys' } {
  $element=Resolve-Control $request.element
  Assert-Owner $element
  if ($element.Current.IsPassword -or -not $element.Current.IsEnabled) { throw 'Password or disabled control rejected' }
  if ($element.Current.ClassName -eq 'Edit' -and ([MaxWindowApi]::GetWindowLong([IntPtr]$element.Current.NativeWindowHandle,-16) -band 0x20)) { throw 'Password edit rejected' }
  switch ($request.action) {
   'invoke' {
    $pattern=$null
    if ($element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)) { $pattern.Invoke() }
    elseif ($element.Current.ClassName -in 'Button','CustButton') {
     $handle=[IntPtr]$element.Current.NativeWindowHandle
     if ($handle -eq [IntPtr]::Zero) { throw 'Control has no native handle' }
     [uint32]$owner=0; [void][MaxWindowApi]::GetWindowThreadProcessId($handle,[ref]$owner)
     if ($owner -ne $targetId) { throw 'Foreign native control' }
     if ($element.Current.ClassName -eq 'Button') {
      if (-not [MaxWindowApi]::PostMessage($handle,0xF5,[IntPtr]::Zero,[IntPtr]::Zero)) { throw 'Button activation could not be queued' }
     } else {
      # Max CustButton does not expose UIA Invoke. Queue a local client-area click.
      if (-not [MaxWindowApi]::PostMessage($handle,0x201,[IntPtr]1,[IntPtr]65537)) { throw 'Button press could not be queued' }
      if (-not [MaxWindowApi]::PostMessage($handle,0x202,[IntPtr]::Zero,[IntPtr]65537)) { throw 'Button release could not be queued; outcome unknown' }
     }
    } else { throw 'Control does not support InvokePattern or a known native button class' }
   }
   'set_value' {
    $pattern=$null
    if ($element.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)) {
     if ($pattern.Current.IsReadOnly) { throw 'Read-only control' }
     $pattern.SetValue([string]$request.value)
     $readback=$pattern.Current.Value
    } elseif ($element.Current.ClassName -eq 'Edit') {
     $handle=[IntPtr]$element.Current.NativeWindowHandle
     [uint32]$owner=0; [void][MaxWindowApi]::GetWindowThreadProcessId($handle,[ref]$owner)
     if ($owner -ne $targetId) { throw 'Foreign native edit' }
     $style=[MaxWindowApi]::GetWindowLong($handle,-16)
     if (($style -band 0x800) -or ($style -band 0x20)) { throw 'Read-only or password edit' }
     $nativeResult=[IntPtr]::Zero
     if ([MaxWindowApi]::SendMessageTimeout($handle,0xC,[IntPtr]::Zero,[string]$request.value,2,2000,[ref]$nativeResult) -eq [IntPtr]::Zero) { throw 'Set text timed out or failed; outcome unknown' }
     $text=[Text.StringBuilder]::new(16001)
     if ([MaxWindowApi]::ReadText($handle,0xD,[IntPtr]$text.Capacity,$text,2,2000,[ref]$nativeResult) -eq [IntPtr]::Zero) { throw 'Text readback timed out; re-inspect' }
     $readback=$text.ToString()
    } else { throw 'Control does not support ValuePattern or a standard native Edit' }
    if ($readback -cne [string]$request.value) { throw 'Control value differs from requested text; re-inspect before retrying' }
   }
   'send_keys' {
    if ($request.keys.Contains('%') -or $request.keys -match '(?i)\{(LWIN|RWIN|APPS|PRTSC|BREAK)' -or ($request.keys.Contains('^') -and $request.keys -match '(?i)\{ESC')) { throw 'Alt and global shortcuts rejected' }
    [void][MaxWindowApi]::SetForegroundWindow([IntPtr]([long]$request.element.hwnd))
    $nativeFocus=$false
    try { $element.SetFocus() } catch {
     $handle=[IntPtr]$element.Current.NativeWindowHandle
     [uint32]$owner=0; [void][MaxWindowApi]::GetWindowThreadProcessId($handle,[ref]$owner)
     if ($handle -eq [IntPtr]::Zero -or $owner -ne $targetId) { throw 'Control cannot receive focus' }
     $nativeFocus=[MaxWindowApi]::FocusNative($handle)
    }
    if (-not $nativeFocus) {
     $focused=[System.Windows.Automation.AutomationElement]::FocusedElement
     if ($null -eq $focused -or (($focused.GetRuntimeId() -join ',') -ne ($element.GetRuntimeId() -join ','))) { throw 'Requested control did not gain focus; input rejected' }
    }
    [uint32]$foregroundPid=0
    [void][MaxWindowApi]::GetWindowThreadProcessId([MaxWindowApi]::GetForegroundWindow(),[ref]$foregroundPid)
    if ($foregroundPid -ne $targetId) { throw 'Max is not foreground; input rejected' }
    [Windows.Forms.SendKeys]::SendWait([string]$request.keys)
   }
  }
  $answer=@{action=$request.action;completed=$true;reinspect=$true}
  if ($request.action -eq 'set_value') { $answer.value=$readback }
  if ($request.action -eq 'invoke') { $answer.completed=$false; $answer.dispatched=$true }
  $answer | ConvertTo-Json -Compress
 }
 default { throw 'Unknown UI action' }
}
