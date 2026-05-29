# M3 FABs

A FAB represents the screen's primary *creation* action — add an item, compose a message, start a new thing. It is not for contextual actions on existing content (save, submit, next); use `FilledButton` for those. See [`m3-foundations.md`](../m3-foundations.md#action-emphasis-hierarchy) for the full button hierarchy.

## When to use each pattern

| Scenario | Pattern | Example |
|----------|---------|---------|
| Single primary action | Standard FAB | Invoice list: sync button |
| Multiple distinct actions | Expandable FAB menu | Recipe list: add + import |
| Two variants of same action | Segmented FAB | (rare — e.g., upload photo / upload file) |

Never stack multiple full-size FABs in a column — it's non-standard M3 and visually cluttered. Use the expandable menu pattern below.

## Expandable FAB Menu

The main FAB opens a menu of labeled action items. Tapping it again (or executing an action) closes the menu.

### State management

Add `_fabOpen` state and `SingleTickerProviderStateMixin` to the page:

```dart
class _MyPageState extends ConsumerState<MyPage>
    with SomeMixin, SingleTickerProviderStateMixin {
  bool _fabOpen = false;

  void _toggleFab() => setState(() => _fabOpen = !_fabOpen);

  void _closeFab() {
    if (_fabOpen) setState(() => _fabOpen = false);
  }
}
```

### Building the FAB

The main FAB uses `Icons.add` and rotates 45deg when open. Menu items stack above it.

```dart
Widget _buildExpandableFab(BuildContext context) {
  return Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      if (_fabOpen) ...[
        _FabMenuItem(
          label: 'Import from Drive',
          icon: const Icon(Icons.sync),
          onTap: () {
            _closeFab();
            sync();
          },
        ),
        const SizedBox(height: 8),
        _FabMenuItem(
          label: 'New recipe',
          icon: const Icon(Icons.restaurant_outlined),
          onTap: () {
            _closeFab();
            context.push('/recipes/new');
          },
        ),
        const SizedBox(height: 12),
      ],
      FloatingActionButton(
        onPressed: _toggleFab,
        shape: const CircleBorder(),
        child: AnimatedRotation(
          turns: _fabOpen ? 0.125 : 0,
          duration: const Duration(milliseconds: 200),
          child: const Icon(Icons.add),
        ),
      ),
    ],
  );
}
```

### Menu item widget

Each menu item is a label chip + small FAB, right-aligned:

```dart
class _FabMenuItem extends StatelessWidget {
  const _FabMenuItem({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final Widget icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Material(
          elevation: 2,
          borderRadius: BorderRadius.circular(8),
          color: theme.colorScheme.surfaceContainerHigh,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Text(label, style: theme.textTheme.labelMedium),
          ),
        ),
        const SizedBox(width: 12),
        FloatingActionButton.small(
          heroTag: label,
          onPressed: onTap,
          child: icon,
        ),
      ],
    );
  }
}
```

## Guidelines

- **Close before acting**: always call `_closeFab()` before executing the action.
- **Descriptive icons**: each action gets its own icon (e.g., `Icons.sync` for import, `Icons.restaurant_outlined` for new recipe).
- **Unique heroTags**: every `FloatingActionButton` in the same widget tree needs a unique `heroTag` — using `label` works well.
- **Loading state**: if an action is async (like sync), swap the icon for a `CircularProgressIndicator` and disable `onTap` while in progress.

## Reference implementation

See `features/recipes/views/recipe_list_page.dart` for a working expandable-FAB example.
