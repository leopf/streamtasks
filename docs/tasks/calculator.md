---
title: Calculator
parent: Tasks
---
# Calculator

## Inputs
The Calculator has a configurable amout of inputs. A veriable name is assigned to each input, that can be used in the formula to calculate the output.

## Outputs
* **output** - the output value calculated with the formula.

## Configuration
Global:
* **formula** - The mathematical formula to calculate the output
* **synchronized** - Whether the inputs should be synchronized.

Per Input:
* **default value** - the default value of the input variable
* **variable name** - the name of the variable assigned to this input

## Description
The Calculator Task is a mathematical processing task that evaluates a given formula using input values and produces an output value.

The Math Engine is a simple calculator language that allows you to evaluate mathematical expressions. It supports a wide range of arithmetic operations, comparison operators, logical operators, and built-in mathematical functions. This user manual provides an overview of the math syntax and how to use it effectively.

### Basic Arithmetic Operations

The Math Engine supports the following basic arithmetic operations:

*   Addition: Use the `+` operator to add two numbers together. For example, `2 + 3` evaluates to `5`.
*   Subtraction: Use the `-` operator to subtract one number from another. For example, `5 - 2` evaluates to `3`.
*   Multiplication: Use the `*` operator to multiply two numbers. For example, `2 * 3` evaluates to `6`.
*   Division: Use the `/` operator to divide one number by another. For example, `6 / 2` evaluates to `3`.
*   Modulo: Use the `%` operator to find the remainder of the division of one number by another. For example, `7 % 3` evaluates to `1`.
*   Exponentiation: Use the `**` operator to raise a number to a power. For example, `2 ** 3` evaluates to `8`.

### Comparison Operators

The Math Engine allows you to compare numbers using the following operators:

*   Greater Than: Use the `>` operator to check if one number is greater than another. For example, `5 > 3` evaluates to `1` (true).
*   Less Than: Use the `<` operator to check if one number is less than another. For example, `2 < 5` evaluates to `1` (true).
*   Greater Than or Equal To: Use the `>=` operator to check if one number is greater than or equal to another. For example, `5 >= 3` evaluates to `1` (true).
*   Less Than or Equal To: Use the `<=` operator to check if one number is less than or equal to another. For example, `2 <= 5` evaluates to `1` (true).
*   Equal To: Use the `==` operator to check if two numbers are equal. For example, `2 == 2` evaluates to `1` (true).
*   Not Equal To: Use the `!=` operator to check if two numbers are not equal. For example, `2 != 3` evaluates to `1` (true).

The comparison operators return `1` if the condition is true and `0` if the condition is false.

### Logical Operators

The Math Engine supports logical operators to perform logical operations on boolean values. In the Math Engine, any non-zero value is considered true, and `0` is considered false. The logical operators include:

*   Logical AND: Use the `&` operator to perform a logical AND operation between two boolean values. For example, `1 & 0` evaluates to `0` (false).
*   Logical OR: Use the `|` operator to perform a logical OR operation between two boolean values. For example, `1 | 0` evaluates to `1` (true).
*   Logical XOR: Use the `^` operator to perform a logical XOR operation between two boolean values. For example, `1 ^ 0` evaluates to `1` (true).

### Parentheses for Grouping

You can use parentheses `(` and `)` to group expressions and control the order of operations. Expressions inside parentheses are evaluated first. For example, `(2 + 3) * 4` evaluates to `20` because the addition is performed before the multiplication.

### Variables

The Math Engine allows you to use variables in your expressions. A variable is a named value that can be assigned a number or an expression. To use a variable, simply type its name. For example, if you have assigned `x = 2`, you can use `x` in your expressions.

### Constants

The Math Engine provides two constants:

*   π (pi): Use `pi` to represent the mathematical constant π (approximately 3.14159).
*   e (Euler's number): Use `e` to represent the mathematical constant e (approximately 2.71828).

### Built-in Mathematical Functions

The Math Engine provides a set of built-in mathematical functions that you can use in your expressions. These functions include:

*   Trigonometric functions: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`
*   Hyperbolic functions: `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh`
*   Logarithmic functions: `log`, `log2`, `log10`
*   Exponential and square root functions: `exp`, `sqrt`
*   Rounding functions: `floor`, `ceil`, `round`
*   Absolute value function: `abs`
*   Minimum and maximum functions: `min`, `max`

To use a function, type the function name followed by parentheses `()`. If the function requires arguments, specify them inside the parentheses. For example, `sin(0.5)` calculates the sine of `0.5`.

### Conditional Expressions

The Math Engine supports conditional expressions using the inline if-else syntax. The syntax for a conditional expression is as follows:

`condition ? expression_if_true : expression_if_false`

The `condition` is evaluated first. If the condition is true (non-zero), the `expression_if_true` is evaluated and returned. Otherwise, the `expression_if_false` is evaluated and returned. For example, `x > 0 ? 1 : -1` returns `1` if `x` is greater than `0`, and `-1` otherwise.

### Examples

Here are some examples of valid Math Engine expressions:

*   Arithmetic: `2 + 3`, `5 - 2`, `2 * 3`, `6 / 2`, `7 % 3`, `2 ** 3`
*   Comparison: `5 > 3`, `2 < 5`, `5 >= 3`, `2 <= 5`, `2 == 2`, `2 != 3`
*   Logical: `1 & 0`, `1 | 0`, `1 ^ 0`
*   Grouping: `(2 + 3) * 4`
*   Variables: `x + y`, where `x = 2` and `y = 3`
*   Constants: `2 * pi`, `e ** 2`
*   Functions: `sin(0.5)`, `log10(100)`, `sqrt(16)`
*   Conditional: `x > 0 ? 1 : -1`, where `x = 2`

### Limitations

*   The Math Engine does not support complex numbers or vector operations.
*   The Math Engine grammar is case-sensitive, so make sure to use consistent casing for variable names and function calls.
*   Division (`/`) always performs floating-point division, even if both operands are integers.