package main.java.org.app;

import main.java.org.app.parser.Parser;
import main.java.org.app.printer.Printer;
import main.java.org.app.utils.exception.FilePathException;

public class AppController {

    public void run(String[] args) throws FilePathException {

        var filePath = getFilePath(args);
        var info = new Parser().parseLogFile(filePath);
        new Printer().printLogMessage(info);

    }

    private String getFilePath(String[] args) throws FilePathException {

        String filePath;

        if (args.length == 0) {
            throw new FilePathException("The file path is missing!");
        }
        filePath = args[0];

        return filePath;
    }

}
