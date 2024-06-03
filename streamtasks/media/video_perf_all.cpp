#include <pybind11/pybind11.h>
#include <limits>
#include <pybind11/stl.h>

#define ALPHA_PIXEL_SIZE 4

namespace py = pybind11;

py::bytes merge_images(std::vector<py::bytes> images, bool alpha_front) {
    size_t image_count = images.size();
    assert(image_count > 0);

    std::vector<uint8_t*> image_data;
    size_t image_size = std::numeric_limits<size_t>::max();
    for (size_t i = 0; i < image_count; i++)
    {
        std::basic_string_view<char> v(images[i]);
        image_size = std::min(image_size, v.size());
        image_data.push_back((uint8_t*)v.data());
    }
    
    std::string out_str(image_size, '\0');
    uint8_t* out_data = (uint8_t*)out_str.data();

    for (size_t offset = 0; offset < image_size; offset += ALPHA_PIXEL_SIZE)
    {
        uint8_t* out_cv;
        if (alpha_front) 
        {
            out_data[offset] = 255;
            out_cv = &out_data[offset + 1];
        }
        else 
        {
            out_data[offset + ALPHA_PIXEL_SIZE - 1] = 255;
            out_cv = &out_data[offset];
        }

        for (size_t i = 0; i < image_count; i++)
        {
            uint8_t* frame_cv;
            uint16_t alpha;

            if (alpha_front) 
            {
                alpha = image_data[i][offset];
                frame_cv = &image_data[i][offset + 1];
            }
            else 
            {
                alpha = image_data[i][offset + ALPHA_PIXEL_SIZE - 1];
                frame_cv = &image_data[i][offset];
            }

            uint16_t alpha_old = 255 - alpha;
            for (size_t c = 0; c < ALPHA_PIXEL_SIZE - 1; c++)
            {
                out_cv[c] = (uint8_t)((alpha_old * out_cv[c] + alpha * frame_cv[c]) / 255);
            }
        }
    }

    return py::bytes(out_str);
}

PYBIND11_MODULE(video_perf, m) {
    m.def("merge_images", &merge_images);
}