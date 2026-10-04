import 'package:flutter/material.dart';

/// Fills the screen when there is room (so Spacer() still pushes buttons to the bottom)
/// and scrolls when there is not (large fonts, small phones, open keyboard).
/// This is what prevents the yellow/black "BOTTOM OVERFLOWED" stripes.
class ScrollFill extends StatelessWidget {
  final Widget child;
  const ScrollFill({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: IntrinsicHeight(child: child),
        ),
      ),
    );
  }
}
