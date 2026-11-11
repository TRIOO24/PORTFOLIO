    import java.net.*;

    class Server {
    public static void main(String args[]) throws Exception {

        DatagramSocket ds = new DatagramSocket(5000);
        byte b[] = new byte[100];

        System.out.println("Server Started");

        DatagramPacket dp = new DatagramPacket(b, b.length);
        ds.receive(dp);

        String s = new String(dp.getData(), 0, dp.getLength());

        System.out.println("Received: " + s);

        ds.close();
    }
    }

    import java.net.*;
    import java.util.*;

    class Client {
    public static void main(String args[]) throws Exception {

        Scanner sc = new Scanner(System.in);

        DatagramSocket ds = new DatagramSocket();

        System.out.print("Enter Message: ");
        String s = sc.nextLine();

        System.out.print("Enter Frame Size: ");
        int n = sc.nextInt();

        InetAddress ip = InetAddress.getByName("localhost");

        for (int i = 0; i < s.length(); i += n) {

            String frame = s.substring(i, Math.min(i+n, s.length()));

            byte b[] = frame.getBytes();

            DatagramPacket dp = new DatagramPacket(b, b.length, ip, 5000);

            ds.send(dp);

            System.out.println("Frame Sent: " + frame);
        }

        ds.close();
    }
    }  
