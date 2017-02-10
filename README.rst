OpenStack Swift middleware for serverless functions
===================================================
In DevStack::

    enable Swift
    enable Picasso

After DevStack install::

    clone https://github.com/denismakogon/serverless-functions-middleware
    install develop or regular install

Modify Swift proxy conf by adding::

    [filter:functions_middleware]
    use = egg:functions#functions_middleware

In **[pipeline:main]** section add **functions_middleware** to the list of other middleware in **pipeline** config option
Restart Swift proxy service by::

    screen -x
    Ctrl+A,n to find s-proxy window
    Restart process

