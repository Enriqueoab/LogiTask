package main.java.org.app.fileInfo;

public class FileInfo {

    private int seqNum;

    private String message;

    public FileInfo(int seqNum, String message) {
        this.seqNum = seqNum;
        this.message = message;
    }

    public int getSeqNum() {
        return seqNum;
    }

    public String getMessage() {
        return message;
    }
}
