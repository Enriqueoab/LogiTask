package main.java.org.app;

import main.java.org.app.utils.exception.FilePathException;

public class Main {

    public static void main(String[] args) throws FilePathException {
        new AppController().run(args);
    }

}