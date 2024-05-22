package main.java.org.app.printer;

import java.util.List;
import java.util.Arrays;
import java.util.stream.Stream;
import main.java.org.app.fileInfo.FileInfo;
import main.java.org.app.utils.constant.PrintConstant;

public class Printer {

    public void printLogMessage(List<FileInfo> fileInfo) {

        printTableHeader();
        fileInfo.stream()
                .flatMap(info -> Stream.concat(formatFileInfo(info), Stream.of("")))
                .forEach(System.out::println);
        System.out.print(PrintConstant.SEPARATOR);
    }

    private static Stream<String> formatFileInfo(FileInfo fileInfo) {
        String[] lines = fileInfo.getMessage().split("\n");
        var seqNum = fileInfo.getSeqNum();
        return Stream.concat(
                Stream.of(String.format(PrintConstant.ROW_FORMAT, seqNum, lines[0])),
                Arrays.stream(lines, 1, lines.length).map(line -> String.format(PrintConstant.ROW_FORMAT, "", line))
        );
    }

    private void printTableHeader() {
        System.out.printf(PrintConstant.HEADER_FORMAT, PrintConstant.SEQ_NUM, PrintConstant.MESSAGE);
        System.out.println(PrintConstant.SEPARATOR);
    }

}
