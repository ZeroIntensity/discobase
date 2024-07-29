---
hide:
    - navigation
---

# Discord Interface
A handful of essential commands are readily available for interacting with the Discobase discord bot.

!!! note

    The commands shown in the example section will generally have a interface provided by Discord.
    In these examples, we use a **Games** table which has the columns: **Title** and **Genre**.

## Access the Table's Schema
Checkout the data type for the columns in your table before performing `insert` or `update` operations.

The `/schema` operation takes in the name of your table as input and outputs information such as the names of columns and their datatypes you have set them to. 

### Example
`/schema Games`

### Limitation
Considering the limit of fields is 25 on discord. The command can only show up to 25 columns, so we'll signify the limit as `field_length = 25` forming the following inequality: 

**C** <= `field_length` where **C** is the number of columns.

## Update a Column's Value
Users can modify the arbitrary value they have set to a specific column in their data; however, the data type has to be consistent with the column's data type. 

The `/update` slash command takes the following parameters: the name of the table, the name of the column, the old value, and the new value that should replace the old one.

### Example
`/update Games Genre Puzzle Action`

### Limitation
The user is disallowed from entering a new value that is not consistent with the predefined column's data type.
