# Gmail-Unread
This small python script checks all unread E-Mails from GMail and notifies the user about them via Matrix Chat.
This can be useful if you consiously use a separate E-Mail address for important accounts for which you (by choice) don't have access from on your mobile devices.
With this script you can be notified if there are unread E-Mails on this account, from who they are and what subject they have.

This script uses the minimal required privilege required to fetch new Gmails and get their FROM address and subject (not more than that, just the address and subject), to minimize risk if the token gets exposed.
