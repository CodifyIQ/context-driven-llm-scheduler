# Destructive Actions

The rule for using `colorScheme.error` on destructive flows, in one line: **color the commit, not the trigger.**

## Where error color belongs

The button or menu item that *performs* the destructive action gets error styling. Concretely:

- **Menu item text labels** for destructive items (`Delete`, `Discard`, `Remove`) — see [`menus.md`](menus.md).
- **The confirm button of an `AlertDialog`** that commits the action.

In both cases, the user is about to commit. Red signals "this is the last chance to back out."

## Where error color does NOT belong

A **standalone destructive icon button** — e.g. a trash can in an app bar, list row, or toolbar — should **not** be tinted with `colorScheme.error`. Use the default icon color (`onSurfaceVariant`, or whatever the surrounding `IconTheme` provides).

The icon button merely *opens the path* to a destructive action; it doesn't commit one. Painting every trash icon red turns the UI into a field of alarm bells and trains users to ignore the signal exactly where it matters — at the confirm step.

The destructive *meaning* of an icon button is already carried by:

- The icon shape itself (`Icons.delete_outline`, `Icons.archive_outlined`, etc.)
- The tooltip / semantic label ("Delete")
- The confirmation step that follows the tap

## Examples

```dart
// ✅ Default-colored icon — destructive meaning carried by the shape + tooltip
IconButton(
  icon: const Icon(Icons.delete_outline),
  tooltip: 'Delete',
  onPressed: _confirmDelete,
)

// ❌ Don't tint standalone icon buttons with error
IconButton(
  icon: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.error),
  tooltip: 'Delete',
  onPressed: _confirmDelete,
)

// ✅ DO use error color on the menu item that names the action
MenuItemButton(
  leadingIcon: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.error),
  onPressed: _confirmDelete,
  child: Text(
    'Delete',
    style: TextStyle(color: Theme.of(context).colorScheme.error),
  ),
)

// ✅ DO use error color on the confirm button of the AlertDialog
showDialog(
  context: context,
  builder: (context) => AlertDialog(
    title: const Text('Delete item?'),
    content: const Text('This cannot be undone.'),
    actions: [
      TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
      FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: Theme.of(context).colorScheme.error,
          foregroundColor: Theme.of(context).colorScheme.onError,
        ),
        onPressed: _onConfirmDelete,
        child: const Text('Delete'),
      ),
    ],
  ),
)
```

## Accessibility

Color is never a sufficient cue on its own. Every destructive action should also carry meaning through the icon shape and the visible/aural label — so users with color-vision differences or screen readers get the same signal sighted users get from red.
