import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  readonly property string cli: Quickshell.env("HOME") + "/.local/bin/hypr-control-cli"
  property var data: ({})
  property bool busy: snapshotProc.running || actionProc.running
  property string error: ""
  property string pendingSuccessMessage: ""
  property string snapshotError: ""
  property string actionError: ""

  signal refreshed()
  signal actionFinished(bool success, string message)

  function refresh() {
    if (snapshotProc.running) return
    snapshotError = ""
    snapshotProc.running = true
  }

  function run(args, successMessage) {
    if (actionProc.running) return
    actionError = ""
    pendingSuccessMessage = successMessage || "Setting applied."
    actionProc.command = [cli].concat(args)
    actionProc.running = true
  }

  Process {
    id: snapshotProc
    command: [root.cli, "snapshot"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.data = JSON.parse(String(text || "{}"))
          root.error = ""
          root.refreshed()
        } catch (parseError) {
          root.error = "Could not parse system settings: " + parseError
        }
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.snapshotError = String(text || "").trim()
    }
    onExited: function(exitCode) {
      if (exitCode !== 0)
        root.error = root.snapshotError || "Could not read system settings."
    }
  }

  Process {
    id: actionProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.actionError = String(text || "").trim()
    }
    onExited: function(exitCode) {
      if (exitCode === 0) {
        root.error = ""
        root.actionFinished(true, root.pendingSuccessMessage)
        root.refresh()
      } else {
        var message = root.actionError || "Could not apply the setting."
        root.error = message
        root.actionFinished(false, message)
      }
    }
  }
}
