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

![schema](assets/schema_cmd.gif)

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

## Retrieve Statistics Concerning your Database
Knowing pertinent information such as how many tables are in my database and what are the names of each table are easily answered using this command.

`/tablestats` iterates over your database's tables to display the names you've assigned to them and it tallies up a count of how many you've made.

### Example
`/tablestats Games`

### Limitation
There are no limitations for this command.

## Perform a Search on your Data
Finding information in your data is an essential task.

The slash command `/find`will ask for the following information before performing a search such as the name of the table, the name of the column, and the value you want to look up.

### Example
`/find Games Genre Action`

### Limitation
The `description` field in a rich embed is limited to `4096` characters.