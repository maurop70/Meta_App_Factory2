
Invoke-RestMethod -Uri "http://127.0.0.1:8000/users" `
    -Method GET `
    -Headers @{
        "Authorization" = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJFUlAtMTAwMCIsInJvbGUiOiJBRE1JTklTVFJBVE9SIiwiZGVwYXJ0bWVudCI6IklUIEluZnJhc3RydWN0dXJlIiwibmFtZSI6IlN5c3RlbSBBZG1pbmlzdHJhdG9yIiwiZXhwIjoxNzc4MDg4NjY1LCJqdGkiOiJjNDk4ZWZiZS0wNWY1LTQwNWEtOTMwMy00NjQwM2IxOGY2NWEifQ.Ay-ThEJVnQ29e6EeLPgDkUcPpHP_ZRHoItPm0BdfLN1Rrl1apafgXA4oEAjcAMe3hmvE8HqM9dcu-DumqnXng9m6KTdWaFEGX4-6QrZJZCqbd1ahEzG5PCNUitSWSlili7pESomaRbr0XOG8LU7O559Z3HJbY7lRy3q1YYQhl43tfCyzs0tAasU5WYsnou2uU_7_8WU69jE3kGpv5bsbVRuHZiUEEIB1jaA0jy6w1s_OP9KrtdT9MfZjML46uAmTk8zjB68yFCLtzT8QSi26nkued8_652X1yh8ICYRVAda4qJ-ULBcwenMwZRE-xojd0GLyF1iQWy_DBZBBnFH13A"
        "Content-Type"  = "application/json"
    } -SkipHttpErrorCheck -StatusCodeVariable "status"

Write-Output "Status Code: $status"
