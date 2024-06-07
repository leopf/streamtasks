#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <linux/videodev2.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sstream>
#include <pybind11/embed.h>

#define REQ_BUFFER_COUNT 2
#define REQ_MIN_BUFFER_COUNT REQ_BUFFER_COUNT

#define CLEAR(x) memset(&(x), 0, sizeof(x))
#define THROW_IF(res, value, text) \
    if (res == value)              \
    {                              \
        std::stringstream ss;      \
        ss << "Error: " << text << ", errno: " << errno << " " << strerror(errno); \
        throw std::runtime_error(ss.str()); \
    }

namespace py = pybind11;

static int xioctl(int fd, int req, void *arg)
{
    int res;
    do
    {
        res = ioctl(fd, req, arg);
    } while (-1 == res && EINTR == errno);
    return res;
}

struct frame_buffer
{
    void *start;
    size_t length;
};

class VideoCapture
{
private:
    int fd;
    bool started = false;
    bool closed = false;
    struct v4l2_format format;
    struct v4l2_streamparm params;
    std::vector<frame_buffer> buffers;

    void enqueue_buffer(unsigned int index)
    {
        struct v4l2_buffer buf;
        CLEAR(buf);
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = index;
        THROW_IF(xioctl(fd, VIDIOC_QBUF, &buf), -1, "Failed to queue buffer!");
    }

public:
    VideoCapture(const char *dev_name, v4l2_format *fmt, v4l2_streamparm *p)
    {
        struct stat st;
        THROW_IF(stat(dev_name, &st), -1, "Can not identify dev file!");
        if (!S_ISCHR(st.st_mode))
        {
            throw std::runtime_error("File is not a char device!");
        }
        fd = open(dev_name, O_RDWR, 0);
        THROW_IF(fd, -1, "Failed to open device!");

        struct v4l2_capability cap;
        THROW_IF(xioctl(fd, VIDIOC_QUERYCAP, &cap), -1, "Device is not a V4L2 device!");
        if (!(cap.capabilities & V4L2_CAP_VIDEO_CAPTURE))
            throw std::runtime_error("Device is not a V4L2 capture device!");
        if (!(cap.capabilities & V4L2_CAP_STREAMING))
            throw std::runtime_error("Device does not support streaming!");

        memcpy(&format, fmt, sizeof(v4l2_format));
        THROW_IF(xioctl(fd, VIDIOC_S_FMT, &format), -1, "Failed to set format!");
        // TODO: check if width/height changed

        if (p != NULL) {
            memcpy(&params, p, sizeof(v4l2_streamparm));
            THROW_IF(xioctl(fd, VIDIOC_S_PARM, &params), -1, "Failed to set params!");
        }
        else {
            CLEAR(params);
            params.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            THROW_IF(xioctl(fd, VIDIOC_G_PARM, &params), -1, "Failed to get params!");
        }

        unsigned int min;
        min = format.fmt.pix.width * 2;
        if (format.fmt.pix.bytesperline < min)
            format.fmt.pix.bytesperline = min;
        min = format.fmt.pix.bytesperline * format.fmt.pix.height;
        if (format.fmt.pix.sizeimage < min)
            format.fmt.pix.sizeimage = min;

        struct v4l2_requestbuffers req;
        CLEAR(req);
        req.count = REQ_BUFFER_COUNT;
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        req.memory = V4L2_MEMORY_MMAP;

        THROW_IF(xioctl(fd, VIDIOC_REQBUFS, &req), -1, "Failed to request buffers!");

        if (req.count < REQ_MIN_BUFFER_COUNT)
            throw std::runtime_error("Insufficient buffer memory!");

        for (size_t i = 0; i < req.count; i++)
        {
            struct v4l2_buffer buf;
            CLEAR(buf);
            buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            buf.memory = V4L2_MEMORY_MMAP;
            buf.index = i;

            THROW_IF(xioctl(fd, VIDIOC_QUERYBUF, &buf), -1, "Failed to query buffer!");
            struct frame_buffer fbuf = {.start = mmap(NULL, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buf.m.offset), .length = buf.length};
            if (MAP_FAILED == fbuf.start)
                throw std::runtime_error("Failed to map buffer into memory!");
            buffers.push_back(fbuf);
        }
    }
    ~VideoCapture()
    {
        close_device();
    }

    unsigned int get_width() {
        return format.fmt.pix.width;
    }
    unsigned int get_height() {
        return format.fmt.pix.height;
    }
    unsigned int get_pixelformat() {
        return format.fmt.pix.pixelformat;
    }
    struct v4l2_fract *get_framerate() {
        return &(params.parm.capture.timeperframe);
    }

    std::string read_frame()
    {
        struct v4l2_buffer buf;
        CLEAR(buf);
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        THROW_IF(xioctl(fd, VIDIOC_DQBUF, &buf), -1, "Failed to dequeue buffer!");

        if (buf.index >= buffers.size())
            throw std::runtime_error("Dequeued buffer is out of range!");

        std::string result((char *)buffers[buf.index].start, buf.bytesused);
        enqueue_buffer(buf.index);

        return result;
    }
    void start()
    {
        if (started)
            throw std::runtime_error("Capture already started!");
        for (size_t i = 0; i < buffers.size(); i++)
            enqueue_buffer(i);

        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        THROW_IF(xioctl(fd, VIDIOC_STREAMON, &type), -1, "Failed to start stream!");
        started = true;
    }
    void stop()
    {
        if (!started)
            throw std::runtime_error("Capture not started!");
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        THROW_IF(xioctl(fd, VIDIOC_STREAMOFF, &type), -1, "Failed to stop stream!");
        started = false;
    }
    void close_device()
    {
        if (closed)
            return;
        for (size_t i = 0; i < buffers.size(); i++)
            THROW_IF(munmap(buffers[i].start, buffers[i].length), -1, "Failed to unmap buffer!");
        THROW_IF(close(fd), -1, "Failed to close device!");
        closed = true;
    }
};

const static std::map<std::string, unsigned int> py_pixel_format_map = {
    {"rgb24", V4L2_PIX_FMT_RGB24},
    {"bgra", V4L2_PIX_FMT_BGRA32},
    {"gray", V4L2_PIX_FMT_GREY},
    {"bgr24", V4L2_PIX_FMT_BGR24}};

VideoCapture* py_create_video_capture(const char* dev_name, unsigned int width, unsigned int height, const std::string pixel_format, const py::object& rate)
{
    struct v4l2_format format;
    CLEAR(format);

    format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    format.fmt.pix.width = width;
    format.fmt.pix.height = height;
    format.fmt.pix.pixelformat = py_pixel_format_map.at(pixel_format);
    format.fmt.pix.field = V4L2_FIELD_NONE;

    struct v4l2_streamparm params;
    CLEAR(params);

    params.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    params.parm.capture.timeperframe = {
        .numerator = rate.attr("numerator").cast<unsigned int>(),
        .denominator = rate.attr("denominator").cast<unsigned int>(),
    };

    return new VideoCapture(dev_name, &format, &params);
}

PYBIND11_MODULE(v4l2, m)
{
    py::module fractions = py::module::import("fractions");
    py::object Fraction = fractions.attr("Fraction");
    py::class_<VideoCapture>(m, "VideoCapture")
        .def(py::init<>(&py_create_video_capture))
        .def("start", &VideoCapture::start)
        .def("stop", &VideoCapture::stop)
        .def("read_frame", [](VideoCapture &self) {
            return py::bytes(self.read_frame());
        })
        .def("close", &VideoCapture::close_device)
        .def_property_readonly("width", &VideoCapture::get_width)
        .def_property_readonly("height", &VideoCapture::get_height)
        .def_property_readonly("pixelformat", [](VideoCapture &self) {
            return self.get_pixelformat(); // TODO convert
        })
        .def_property_readonly("framerate", [Fraction](VideoCapture &self) {
            struct v4l2_fract *fr = self.get_framerate();
            return Fraction(fr->numerator, fr->denominator);
        })
        ;
}