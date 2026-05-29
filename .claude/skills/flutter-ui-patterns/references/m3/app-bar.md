# M3 App Bar Actions

The app bar is a tight space — pick what goes in it deliberately. The pattern below applies to detail/item pages where you have one or two primary actions plus a handful of secondary/destructive ones.

## Pattern

- **Primary actions** → `IconButton` directly in `actions:`, icon-only with a `tooltip`. No labels — they steal width.
- **Secondary / destructive actions** → overflow menu (three-dot) at the end of `actions:`. See [`menus.md`](menus.md) for the menu itself.

This keeps the bar compact, leaves room for the title, and matches M3 behavior across iOS / Android / web.

```dart
AppBar(
  title: Text(item.name),
  actions: [
    // Primary action — icon only, no label
    IconButton(
      onPressed: () => context.push('/items/$id/edit'),
      icon: const Icon(Icons.edit_outlined),
      tooltip: 'Edit',
    ),
    // Overflow menu — secondary / destructive actions
    PopupMenuButton<String>(
      onSelected: (value) {
        if (value == 'delete') _confirmDelete();
      },
      itemBuilder: (context) => [
        const PopupMenuItem(
          value: 'delete',
          child: ListTile(
            leading: Icon(Icons.delete_outline),
            title: Text('Delete'),
            contentPadding: EdgeInsets.zero,
          ),
        ),
      ],
    ),
  ],
)
```

## Rules

- **Cap at 2 visible icon actions.** Anything more crowds the title and forces ellipsis. Push the rest into the overflow menu.
- **Don't color icon actions with `colorScheme.error`** — even for a delete icon. See [`destructive-actions.md`](destructive-actions.md) for why ("color the commit, not the trigger").
- **Every `IconButton` needs a `tooltip`.** Icon-only buttons are unreadable to screen readers and ambiguous to first-time users without one.
- **Prefer `MenuAnchor` over `PopupMenuButton` for new code.** `PopupMenuButton` is fine to keep where it already works — don't rewrite just to swap APIs.
