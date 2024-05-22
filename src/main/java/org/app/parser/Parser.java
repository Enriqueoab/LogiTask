package main.java.org.app.parser;

import java.util.List;
import java.nio.ByteOrder;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.io.IOException;
import java.io.FileInputStream;
import main.java.org.app.fileInfo.FileInfo;

public class Parser {

    private static final int INTEGER_BYTE_SIZE = 4;

    public List<FileInfo> parseLogFile(String filePath)  {
        List<FileInfo> info = new ArrayList<>();

        try (FileInputStream fis = new FileInputStream(filePath)) {

            while (fis.available() > 0) {
                var messageSize = readIntFromStream(fis);
                var sequenceNumber = readIntFromStream(fis);
                var message = readMessageFromStream(fis, messageSize);

                info.add(new FileInfo(sequenceNumber, message));
            }
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        return info;
    }


    private int readIntFromStream(FileInputStream fis) throws IOException {
        byte[] buffer = new byte[INTEGER_BYTE_SIZE];
        if (fis.read(buffer) != buffer.length) {
            throw new IOException("Unexpected end of file while reading integer.");
        }
        return ByteBuffer.wrap(buffer).order(ByteOrder.LITTLE_ENDIAN).getInt();
    }

    private String readMessageFromStream(FileInputStream fis, int messageSize) throws IOException {
        var messageBytes = new byte[messageSize];
        if (fis.read(messageBytes) != messageBytes.length) {
            throw new IOException("Unexpected end of file while reading message!");
        }
        return new String(messageBytes);
    }

}
